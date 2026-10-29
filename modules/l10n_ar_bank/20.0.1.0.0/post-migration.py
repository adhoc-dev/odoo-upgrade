"""Restore the BCRA code of the banks and of the bank accounts after the upgrade to 20.

Reads what scripts/pre_odoo/190_200/020-backup_res_bank.py backed up on the old database. The banks,
their xmlids and the bank of each account are already back (modules/base_bank/20.0.1.0.0/post-migration.py),
so the banks of the catalog were updated from the data of this module instead of created again.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BANK_TABLE = "res_bank_bu"
XMLID_TABLE = "res_bank_xmlid_bu"
BANK_NUMBER_TABLE = "res_bank_bank_number_bu"


def _restore_bank_numbers(cr):
    # The banks of the catalog take it from the data; the rest, from 19.
    cr.execute(
        SQL(
            """
            UPDATE res_bank b
               SET bank_number = bu.bank_number
              FROM %(bu)s bu
             WHERE b.id = bu.id
               AND b.bank_number IS NULL
            """,
            bu=SQL.identifier(BANK_NUMBER_TABLE),
        )
    )
    _logger.info("Banks: %s with their BCRA code again", cr.rowcount)


def _merge_into_new_catalog_banks(cr):
    """Merge into the catalog each bank of 19 without xmlid that the catalog of 20 now brings.

    A bank created by hand or by Interbanking, because the catalog of 19 did not have it, would stay
    next to the new bank of the catalog with the same BCRA code.
    """
    cr.execute(
        SQL(
            """
            SELECT DISTINCT ON (dup.id) dup.id, catalog.id
              FROM res_bank dup
              JOIN %(banks)s bu ON bu.id = dup.id
              JOIN ir_model_data cd ON cd.module = 'l10n_ar_bank' AND cd.model = 'res.bank'
              JOIN res_bank catalog ON catalog.id = cd.res_id AND catalog.bank_number = dup.bank_number
             WHERE catalog.id != dup.id
               AND NOT EXISTS (
                       SELECT 1 FROM ir_model_data d
                        WHERE d.model = 'res.bank' AND d.module = 'l10n_ar_bank' AND d.res_id = dup.id
                   )
               AND NOT EXISTS (
                       SELECT 1 FROM %(xmlids)s x WHERE x.module = 'l10n_ar_bank' AND x.name = cd.name
                   )
             ORDER BY dup.id, catalog.id
            """,
            banks=SQL.identifier(BANK_TABLE),
            xmlids=SQL.identifier(XMLID_TABLE),
        )
    )
    mapping = dict(cr.fetchall())
    if not mapping:
        return
    util.replace_record_references_batch(cr, mapping, "res.bank")
    cr.execute(SQL("DELETE FROM res_bank WHERE id IN %s", tuple(mapping)))
    # The name and BIC of the account follow its bank, as in 19.
    cr.execute(
        SQL(
            """
            UPDATE res_partner_bank a
               SET bank_name = b.name,
                   bank_bic = b.bic
              FROM res_bank b
             WHERE a.bank_id = b.id
               AND b.id IN %s
            """,
            tuple(set(mapping.values())),
        )
    )
    _logger.info("Banks: %s merged into the new banks of the catalog", len(mapping))


def _restore_account_clearing(cr):
    # What the account takes from its bank in 20, when the upgrade left it empty.
    cr.execute(
        """
        UPDATE res_partner_bank a
           SET clearing_number = b.bank_number
          FROM res_bank b
         WHERE a.bank_id = b.id
           AND b.bank_number IS NOT NULL
           AND COALESCE(a.clearing_number, '') = ''
        """
    )
    _logger.info("Bank accounts: %s with the BCRA code", cr.rowcount)
    # The BCRA label is created by this module after the label of each account was computed.
    cr.execute(
        "SELECT id FROM res_partner_bank WHERE country_id = %s",
        [util.ref(cr, "base.ar")],
    )
    ids = [account_id for (account_id,) in cr.fetchall()]
    if ids:
        util.recompute_fields(cr, "res.partner.bank", ["clearing_label_id"], ids=ids)


def migrate(cr, version):
    if not util.table_exists(cr, BANK_TABLE):
        _logger.warning("No %s: the BCRA codes were not restored. Did the pre_odoo run?", BANK_TABLE)
        return
    if util.table_exists(cr, BANK_NUMBER_TABLE):
        _restore_bank_numbers(cr)
    if util.table_exists(cr, XMLID_TABLE):
        _merge_into_new_catalog_banks(cr)
    _restore_account_clearing(cr)
