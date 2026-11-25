"""Keep the done quantity of the stock requests as 19 left it.

The post-migration.py of stock_request (OCA) in this version recomputes qty_done,
qty_in_progress and qty_cancelled of the requests with allocations, and does not say which ones
changed. post-recalculated_total.py compares against this copy to tell the customer how many.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Read by post-recalculated_total.py of this same folder.
BACKUP_TABLE = "stock_request_qty_done_bu"


def migrate(cr, version):
    # A copy from an earlier run would compare against other values.
    cr.execute(SQL("DROP TABLE IF EXISTS %s", SQL.identifier(BACKUP_TABLE)))
    if not util.module_installed(cr, "stock_request"):
        return

    # Only the requests the OCA script recomputes: the ones with allocations.
    cr.execute(
        SQL(
            """
            CREATE TABLE %s AS
            SELECT r.id, r.qty_done
              FROM stock_request r
             WHERE EXISTS (SELECT 1 FROM stock_request_allocation a WHERE a.stock_request_id = r.id)
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    _logger.info("stock_request: kept the done quantity of %s requests in %s", cr.rowcount, BACKUP_TABLE)
    cr.execute(SQL("ALTER TABLE %s ADD PRIMARY KEY (id)", SQL.identifier(BACKUP_TABLE)))
