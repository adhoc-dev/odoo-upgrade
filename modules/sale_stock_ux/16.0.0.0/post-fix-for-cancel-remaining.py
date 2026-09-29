from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """ Para que odoo no genere movimientos raros al cancelar remanente tenemos que ajustar el deadline y description picking
    Por lo que vimos en realidad pisar el description_picking no seria necesario
    """
    _logger.debug('Running fix for cancel remaining')
    stock_moves = env['stock.move'].search([('sale_line_id.delivery_status', '=', 'to deliver'), ('state', 'not in', ['cancel', 'done'])])
    for move in stock_moves:
        line = move.sale_line_id
        move.write({
            # 'date_deadline': line.order_id.commitment_date or line.order_id.date_order + datetime.timedelta(days=line.customer_lead or 0.0)),
            'date_deadline': line.order_id.commitment_date or line.order_id.date_order,
            'description_picking': line.name,
            # 'price_unit': new_run_private_method('sale.order.line', '_get_stock_move_price_unit', line.ids),
        })
