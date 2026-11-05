import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

REMOVED_FIELDS = [
    ("stock.move", "picking_partner_id"),
    ("stock.move", "picking_dest_id"),
    ("stock.warehouse.orderpoint", "qty_multiple"),
]


def migrate(cr, version):
    """In 20.0 stock_ux no longer defines these fields. Without this, the favorites,
    saved exports and saved domains that use them fail after the upgrade.

    The two related fields are replaced by their path in domains (picking_id.partner_id,
    move_dest_ids.picking_id); in group by, sort and exports they are removed.
    The reason of stock.return.picking is not here: 20.0 removes the whole wizard."""
    _logger.info("Removing stock_ux fields that 20.0 no longer defines")
    for model, field in REMOVED_FIELDS:
        util.remove_field(cr, model, field)
