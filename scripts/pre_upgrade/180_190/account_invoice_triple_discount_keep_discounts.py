import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import create_backup

_logger = logging.getLogger(__name__)

# Restored by modules/base/19.0.0.0/end-account_invoice_triple_discount_restore_discounts.py.
BACKUP_TABLE = "account_move_line_discounts_bu"


def migrate(cr, version):
    """Keep the invoice line discounts of sale_three_discounts through the install of account_invoice_triple_discount.

    In 18 sale_three_discounts already stores discount1/2/3 on account.move.line, with
    discount as their combination. In 19 it merges into sale_triple_discount, which installs
    account_invoice_triple_discount, and its post_init_hook rewrites those columns:
    discount1 = discount and then discount recomputed from the three, so a line with
    discount2 or discount3 ends with its discounts applied twice. A line with discount over
    100 also breaks the install, against the CHECK (discount1 <= 100) of the module.

    The discounts are backed up here, the lines over 100 get discount 0 so the hook skips
    them, and the end script puts the four columns back.
    """
    cr.execute(SQL("DROP TABLE IF EXISTS %s", SQL.identifier(BACKUP_TABLE)))
    if not util.column_exists(cr, "account_move_line", "discount1"):
        return
    # Not util.module_installed: the merge may have left it in `to install` already.
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'account_invoice_triple_discount' AND state = 'installed'")
    if cr.rowcount:
        # The hook already ran in 18: nothing to protect.
        return

    count = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, discount, discount1, discount2, discount3
          FROM account_move_line
         WHERE COALESCE(discount, 0) != 0
            OR COALESCE(discount1, 0) != 0
            OR COALESCE(discount2, 0) != 0
            OR COALESCE(discount3, 0) != 0
        """,
    )
    cr.execute("UPDATE account_move_line SET discount = 0 WHERE discount > 100")
    _logger.info(
        "Backed up the discounts of %s invoice lines into %s, %s of them over 100%%",
        count,
        BACKUP_TABLE,
        cr.rowcount,
    )
