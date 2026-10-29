"""Restore the banks that Odoo 20 removed from base, with their ids and xmlids, and the bank of each account.

Reads what scripts/pre_odoo/190_200/020-backup_res_bank.py backed up on the old database. base_bank is
new in 20: this runs because modules/base/20.0.0.0/pre-010-base_bank_restore.py forces its scripts.

Each bank keeps its id, so the bank of the accounts and checks is the same id as in 19. Each xmlid
comes back too: the modules that still ship the bank (l10n_ar_bank) find it and update it instead of
creating another one. The bank of the checks and the BCRA code are restored by the modules that own
those columns, l10n_latam_check_ux and l10n_ar_bank.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BANK_TABLE = "res_bank_bu"
XMLID_TABLE = "res_bank_xmlid_bu"
ACCOUNT_TABLE = "res_partner_bank_bank_id_bu"
BANK_FIELDS = [
    "id",
    "name",
    "street",
    "street2",
    "zip",
    "city",
    "state",
    "country",
    "email",
    "phone",
    "active",
    "bic",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
]
# The only modules that ship banks in 20. The xmlids of any other module keep their bank only with
# noupdate: otherwise, when that module is updated, Odoo deletes the records it no longer loads.
MODULES_WITH_BANK_DATA = ("l10n_ar_bank",)


def _restore_banks(cr):
    columns = SQL(", ").join(SQL.identifier(field) for field in BANK_FIELDS)
    cr.execute(
        SQL(
            """
            INSERT INTO res_bank (%(columns)s)
            SELECT %(columns)s
              FROM %(bu)s
                ON CONFLICT (id) DO NOTHING
            """,
            columns=columns,
            bu=SQL.identifier(BANK_TABLE),
        )
    )
    restored = cr.rowcount
    cr.execute("SELECT setval(pg_get_serial_sequence('res_bank', 'id'), GREATEST(MAX(id), 1)) FROM res_bank")
    _logger.info("Banks: %s restored with their id", restored)


def _restore_xmlids(cr):
    if not util.table_exists(cr, XMLID_TABLE):
        return
    cr.execute(
        SQL(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT x.module, x.name, 'res.bank', x.res_id,
                   CASE WHEN x.module IN %(modules)s THEN x.noupdate ELSE TRUE END
              FROM %(bu)s x
              JOIN res_bank b ON b.id = x.res_id
             WHERE NOT EXISTS (
                       SELECT 1 FROM ir_model_data d WHERE d.module = x.module AND d.name = x.name
                   )
            """,
            modules=MODULES_WITH_BANK_DATA,
            bu=SQL.identifier(XMLID_TABLE),
        )
    )
    _logger.info("Banks: %s xmlids restored", cr.rowcount)


def _restore_accounts(cr):
    if not util.table_exists(cr, ACCOUNT_TABLE):
        return
    # In 19 the name and BIC of the account came from its bank: fill them if the upgrade left them empty.
    cr.execute(
        SQL(
            """
            UPDATE res_partner_bank a
               SET bank_id = b.id,
                   bank_name = COALESCE(NULLIF(a.bank_name, ''), b.name),
                   bank_bic = COALESCE(NULLIF(a.bank_bic, ''), b.bic)
              FROM %(bu)s bu
              JOIN res_bank b ON b.id = bu.bank_id
             WHERE a.id = bu.id
               AND a.bank_id IS NULL
            """,
            bu=SQL.identifier(ACCOUNT_TABLE),
        )
    )
    _logger.info("Bank accounts: %s with their bank again", cr.rowcount)


def migrate(cr, version):
    if not util.table_exists(cr, BANK_TABLE):
        _logger.warning("No %s: the banks were not restored. Did the pre_odoo run?", BANK_TABLE)
        return
    _restore_banks(cr)
    _restore_xmlids(cr)
    _restore_accounts(cr)
