import logging

from odoo.upgrade import util
from oba import add_customer_note

_logger = logging.getLogger(__name__)

SAMPLE_SIZE = 20


def migrate(cr, version):
    """Report the operation types that compute the declared value with a pricelist.

    In 20 that price is taken in the unit of the move instead of the product unit, so the
    declared value changes for moves in another unit (a dozen of a product priced per unit).
    Read only: it feeds the customer note and changes nothing.
    """
    _logger.info("Running post-migration of stock_declared_value for version %s", version)
    for column in ("automatic_declare_value", "pricelist_id"):
        if not util.column_exists(cr, "stock_picking_type", column):
            _logger.warning("stock_picking_type.%s is missing: nothing reported", column)
            return

    cr.execute(
        """
        SELECT id FROM stock_picking_type
         WHERE automatic_declare_value AND pricelist_id IS NOT NULL AND active
         ORDER BY id
        """
    )
    type_ids = [row[0] for row in cr.fetchall()]
    env = util.env(cr)
    names = env["stock.picking.type"].browse(type_ids[:SAMPLE_SIZE]).mapped("display_name")

    # Also with zero: the note renders only when the list has something.
    add_customer_note(
        cr,
        {
            "declared_value_pricelist_types_total": len(type_ids),
            "declared_value_pricelist_types": names,
        },
    )
