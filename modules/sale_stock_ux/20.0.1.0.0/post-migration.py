import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recompute the delivery status of the lines of confirmed sale orders left as "no".

    sale.order.line.delivery_status is a stored computed field with default "no":
    the lines that already existed when the module was installed kept the
    default instead of being computed. In 19 that only hid the "cancel
    remaining" button; in 20 the native "To Deliver" filter and its dashboard
    card (sale.order.is_unfulfilled) are computed from it, so those orders would
    disappear from them.
    """
    cr.execute(
        SQL(
            """
            SELECT l.id
              FROM sale_order_line l
              JOIN sale_order o ON o.id = l.order_id
             WHERE o.state = 'sale'
               AND l.display_type IS NULL
               AND (l.delivery_status = 'no' OR l.delivery_status IS NULL)
            """
        )
    )
    ids = [row[0] for row in cr.fetchall()]
    _logger.info("Recomputing the delivery status of %s sale order lines", len(ids))
    util.recompute_fields(cr, "sale.order.line", ["delivery_status"], ids=ids)
