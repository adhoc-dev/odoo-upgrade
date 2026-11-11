"""Bring back the product and the lot of the tickets, which the pass to 20.0 leaves behind.

Reads what scripts/pre_odoo/always/130-backup_helpdesk_ticket_product_lot.py backed up on the
old database. helpdesk_stock drops helpdesk.ticket.product_id and lot_id in 20.0, so Odoo's
upgrade runs without them and the columns go away; helpdesk_stock_ux defines them again and
they are born empty, with the values only in the backup table.

Only products and lots that are still in the database are restored: Odoo's upgrade can take a
record with it, and what could not be put back is reported to the request as a warning.

The backup table is left as it is. The pre_odoo drops it on its next run, so a repeated -u
over the same database restores from it again.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "helpdesk_ticket_product_lot_bu"

# One UPDATE for the whole table: the largest database carries about 11.000 backed up
# tickets. A row where neither the product nor the lot is there is not touched, so a second
# -u over the same database writes nothing.
RESTORE = SQL(
    """
    UPDATE helpdesk_ticket t
       SET product_id = p.id,
           lot_id = l.id
      FROM %s bu
      LEFT JOIN product_product p ON p.id = bu.product_id
      LEFT JOIN stock_lot l ON l.id = bu.lot_id
     WHERE bu.id = t.id
       AND (p.id IS NOT NULL OR l.id IS NOT NULL)
       AND (t.product_id IS DISTINCT FROM p.id OR t.lot_id IS DISTINCT FROM l.id)
    """,
    SQL.identifier(BACKUP_TABLE),
)

# Tickets that are still there but whose product or lot is not: that value is lost, and the
# ticket keeps the rest.
MISSING = SQL(
    """
    SELECT count(*) FILTER (WHERE bu.product_id IS NOT NULL AND p.id IS NULL),
           count(*) FILTER (WHERE bu.lot_id IS NOT NULL AND l.id IS NULL)
      FROM %s bu
      JOIN helpdesk_ticket t ON t.id = bu.id
      LEFT JOIN product_product p ON p.id = bu.product_id
      LEFT JOIN stock_lot l ON l.id = bu.lot_id
    """,
    SQL.identifier(BACKUP_TABLE),
)


def migrate(cr, version):
    if not util.table_exists(cr, BACKUP_TABLE):
        # Not "no ticket had a product": nobody looked. Whoever reads the request has to
        # know the values were never carried over.
        log_message(
            cr,
            "There is no %s: the product and the lot of the tickets were not restored. "
            "Did the pre_odoo script run?" % BACKUP_TABLE,
            "warning",
            module="helpdesk_stock_ux",
        )
        return

    cr.execute(RESTORE)
    _logger.info("Product and lot restored on %s tickets from %s", cr.rowcount, BACKUP_TABLE)

    cr.execute(MISSING)
    products, lots = cr.fetchone()
    if products or lots:
        log_message(
            cr,
            "Tickets left without the value they had: %s without their product and %s without "
            "their lot, because the product or the lot is no longer in the database." % (products, lots),
            "warning",
            module="helpdesk_stock_ux",
        )
