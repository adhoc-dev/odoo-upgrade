"""Tell the customer how many stock requests changed their done quantity in the jump to 20.

From 20.0 a return subtracts what it returns from the done quantity, and in a reception in
several steps only the move that reaches the location of the request counts. The
post-migration.py of stock_request (OCA) in this version recomputes the stored quantities of the
existing requests, so old requests with returns or pushed moves show other numbers. The state
does not change.

The file name sorts after post-migration.py, so it counts right after the OCA script of this
version and before the scripts of stock_request_ux, which change quantities and states for
other reasons. A script that OCA adds in a later version folder runs after this count and is
left out on purpose: the customer note tells the requests recomputed by this fix. If the note
gets to tell every change of the done quantity, both scripts move to 0.0.0.

If 18 or 19 already got the same fix with its own script, nothing changes here and the total
is 0.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import add_customer_note

_logger = logging.getLogger(__name__)

# Written by pre-migration.py of this same folder.
BACKUP_TABLE = "stock_request_qty_done_bu"


def migrate(cr, version):
    if not util.module_installed(cr, "stock_request"):
        return
    if not util.table_exists(cr, BACKUP_TABLE):
        # Nobody looked: a 0 would tell the customer that nothing changed.
        _logger.warning("stock_request: %s does not exist, the recalculated requests were not counted", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            SELECT count(*)
              FROM stock_request r
              JOIN %s b ON b.id = r.id
             WHERE r.qty_done IS DISTINCT FROM b.qty_done
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    total = cr.fetchone()[0]
    _logger.info("stock_request: %s requests changed their done quantity", total)
    # Also with 0: whether the note shows up then is the message's call.
    add_customer_note(cr, {"stock_request_recalculated_total": total})
