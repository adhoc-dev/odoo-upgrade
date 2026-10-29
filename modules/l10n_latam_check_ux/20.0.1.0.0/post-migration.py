"""Restore the issuer bank of each check, that Odoo 20 removed with res.bank.

Reads what scripts/pre_odoo/190_200/020-backup_res_bank.py backed up on the old database. The banks
keep their id of 19 (modules/base_bank/20.0.1.0.0/post-migration.py, that runs before: this module
depends on base_bank), so the bank of the check is the same id.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

CHECK_TABLE = "l10n_latam_check_bank_id_bu"


def migrate(cr, version):
    if not util.table_exists(cr, CHECK_TABLE):
        # Only backed up when l10n_latam_check was installed.
        return
    cr.execute(
        SQL(
            """
            UPDATE l10n_latam_check c
               SET bank_id = b.id
              FROM %(bu)s bu
              JOIN res_bank b ON b.id = bu.bank_id
             WHERE c.id = bu.id
               AND c.bank_id IS NULL
            """,
            bu=SQL.identifier(CHECK_TABLE),
        )
    )
    _logger.info("Checks: %s with their bank again", cr.rowcount)
