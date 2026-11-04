import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Filled by scripts/pre_upgrade/180_190/account_invoice_triple_discount_keep_discounts.py.
BACKUP_TABLE = "account_move_line_discounts_bu"


def migrate(cr, version):
    """Put back the invoice line discounts that the post_init_hook of account_invoice_triple_discount rewrote."""
    if not util.table_exists(cr, BACKUP_TABLE):
        return

    cr.execute(
        SQL(
            """
            UPDATE account_move_line aml
               SET discount = bu.discount,
                   discount1 = bu.discount1,
                   discount2 = bu.discount2,
                   discount3 = bu.discount3
              FROM %s bu
             WHERE aml.id = bu.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    _logger.info("Restored the discounts of %s invoice lines from %s", cr.rowcount, BACKUP_TABLE)
    cr.execute(SQL("DROP TABLE %s", SQL.identifier(BACKUP_TABLE)))
