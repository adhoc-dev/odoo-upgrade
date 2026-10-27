"""Restore the bank catalog and the bank of each bank account after the upgrade to 20.

Reads what scripts/pre_odoo/190_200/020-backup_res_bank.py backed up on the old database.
Odoo 20 removes res.bank from base and l10n_ar_bank defines it again: the banks of the module
are reloaded from its data, and the rest (created by hand or by Interbanking) are created again.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, request_context

_logger = logging.getLogger(__name__)

BANK_TABLE = "res_bank_bu"
ACCOUNT_TABLE = "res_partner_bank_bank_id_bu"
BANK_FIELDS = [
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
]


def _warn(cr, message):
    if request_context(cr):
        log_message(cr, message, "warning")
    else:
        _logger.warning(message)


def _restore_banks(cr):
    """Return {old bank id: bank id in 20}, also kept in the new_id column of BANK_TABLE.

    The migration of l10n_latam_check_ux reads new_id to put back the bank of the checks.
    """
    if not util.column_exists(cr, BANK_TABLE, "new_id"):
        util.create_column(cr, BANK_TABLE, "new_id", "int4")
    cr.execute(
        SQL(
            """
            SELECT bu.id, bu.xmlid_module, bu.xmlid_name, bu.bank_number,
                   d.res_id, b.id, nb.id
              FROM %(bu)s bu
              LEFT JOIN ir_model_data d
                ON d.model = 'res.bank' AND d.module = bu.xmlid_module AND d.name = bu.xmlid_name
              LEFT JOIN res_bank b ON b.id = bu.id AND b.name = bu.name
              LEFT JOIN res_bank nb ON nb.id = bu.new_id
             ORDER BY bu.id
            """,
            bu=SQL.identifier(BANK_TABLE),
        )
    )
    mapping, missing = {}, []
    for (
        old_id,
        xmlid_module,
        _xmlid_name,
        bank_number,
        xmlid_res_id,
        same_id,
        saved_id,
    ) in cr.fetchall():
        if saved_id:
            # Already restored by an earlier run on this database: do not create it twice.
            mapping[old_id] = saved_id
        elif xmlid_module and xmlid_res_id:
            mapping[old_id] = xmlid_res_id
        elif same_id:
            # The upgrade kept the table: the bank is still there.
            mapping[old_id] = same_id
            cr.execute(
                SQL(
                    "UPDATE res_bank SET bank_number = %s WHERE id = %s AND bank_number IS NULL",
                    bank_number,
                    same_id,
                )
            )
        else:
            missing.append(old_id)

    columns = SQL(", ").join(SQL.identifier(field) for field in [*BANK_FIELDS, "bank_number"])
    for old_id in missing:
        cr.execute(
            SQL(
                """
                INSERT INTO res_bank (%(columns)s, create_uid, create_date, write_uid, write_date)
                SELECT %(columns)s, 1, now() at time zone 'UTC', 1, now() at time zone 'UTC'
                  FROM %(bu)s
                 WHERE id = %(old_id)s
             RETURNING id
                """,
                columns=columns,
                bu=SQL.identifier(BANK_TABLE),
                old_id=old_id,
            )
        )
        mapping[old_id] = cr.fetchone()[0]
    for old_id, new_id in mapping.items():
        cr.execute(SQL("UPDATE %s SET new_id = %s WHERE id = %s", SQL.identifier(BANK_TABLE), new_id, old_id))
    _logger.info("Banks: %s mapped, %s created again", len(mapping) - len(missing), len(missing))
    return mapping


def _restore_accounts(cr, mapping):
    if not util.table_exists(cr, ACCOUNT_TABLE):
        _warn(cr, "No %s: the bank of the bank accounts was not restored" % ACCOUNT_TABLE)
        return
    cr.execute(SQL("SELECT id, bank_id FROM %s", SQL.identifier(ACCOUNT_TABLE)))
    restored = 0
    for account_id, old_bank_id in cr.fetchall():
        if old_bank_id not in mapping:
            continue
        cr.execute(
            SQL(
                "UPDATE res_partner_bank SET bank_id = %s WHERE id = %s AND bank_id IS NULL",
                mapping[old_bank_id],
                account_id,
            )
        )
        restored += cr.rowcount
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
    _logger.info(
        "Bank accounts: %s with their bank again, %s with the BCRA code",
        restored,
        cr.rowcount,
    )


def migrate(cr, version):
    if not util.table_exists(cr, BANK_TABLE):
        # Its pre_odoo script always backs up when l10n_ar_bank is installed.
        _warn(cr, "No %s: the banks were not restored. Did the pre_odoo run?" % BANK_TABLE)
        return
    mapping = _restore_banks(cr)
    _restore_accounts(cr, mapping)
