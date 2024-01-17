from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    """ Para que odoo no genere movimientos raros al cancelar remanente tenemos que ajustar el price unit y el deadline
    deadline viene en cero, price unit parece que viene en otra moneda
    Description picking no es necesario por lo que vimos pero es verdad que si se hace nuevo sale con line.name y viene migrado medio feo. asi qeu tmb aprovechamos a escribirlo
    """
    _logger.debug('Running fix for cancel remaining')
    stock_moves = env['stock.move'].search([('purchase_line_id.delivery_status', '=', 'to receive'), ('state', 'not in', ['cancel', 'done'])])
    # stock_moves = env['stock.move'].search([('purchase_line_id.order_id.id', '=', 290), ('purchase_line_id.delivery_status', '=', 'to receive'), ('state', 'not in', ['cancel', 'done'])])
    for move in stock_moves:
        line = move.purchase_line_id
        # ahora no lo necesitamos porque justamente si estan confirmadas no estamos recomputando ni name, ni price, ni nada
        # line._compute_price_unit_and_date_planned_and_name()
        move.write({
            'date_deadline': line.date_planned or line.order_id.date_planned,
            'description_picking': line.name,
            'price_unit': line._get_stock_move_price_unit(),
        })
