import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/stock_currency_valuation/19.0.0.0/post-migration.py, del otro lado del pase.
BACKUP_TABLE = "stock_valuation_layer_currency_bu"
# El salto que borra stock.valuation.layer. La carpeta 180_190 ya lo acota; el rango se
# declara igual para que el gate tenga la misma forma que en el resto de los pre-odoo.
TARGET_VERSION = 19


def migrate(cr, version):
    """Respalda el valor en moneda de cada capa de valuación antes de que el pase la borre.

    En 18, stock_currency_valuation guarda el valor en la moneda de valuación en
    stock.valuation.layer. En 19 ese modelo no existe: el pase lleva el valor de las capas
    al `value` de su movimiento y convierte las revalorizaciones en product.value, pero el
    valor en moneda se pierde.

    Se guarda, por capa, el movimiento al que el pase suma su valor: el propio, o el de la
    capa padre en la diferencia de precio de la factura, que en 18 no tiene movimiento. Las
    revalorizaciones (sin movimiento ni capa padre ni costo en destino) se marcan aparte,
    con producto, descripción y fecha, que es como se las encuentra en product.value. Entran
    también las capas en cero: el costo unitario de una revalorización se reconstruye con la
    cantidad acumulada del producto, y una capa que falta la descuadra.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    # Borra BACKUP_TABLE primero, así una tabla de una corrida anterior no viaja en un
    # request al que el script no aplica. El gate de módulo va acá porque el pre-odoo corre
    # sobre toda la base, sin filtrar por módulo.
    if not should_back_up(
        cr,
        BACKUP_TABLE,
        first_target=TARGET_VERSION,
        last_target=TARGET_VERSION,
        modules=["stock_currency_valuation"],
    ):
        return

    _logger.info("Respaldando el valor en moneda de las capas de valuación en %s", BACKUP_TABLE)
    backed_up = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT l.id,
               l.company_id,
               l.product_id,
               l.lot_id,
               COALESCE(l.stock_move_id, p.stock_move_id) AS move_id,
               (l.stock_move_id IS NULL
                AND l.stock_valuation_layer_id IS NULL
                AND l.stock_landed_cost_id IS NULL) AS is_revaluation,
               l.description,
               l.create_date,
               l.quantity,
               l.value,
               l.value_in_currency
          FROM stock_valuation_layer l
          LEFT JOIN stock_valuation_layer p ON p.id = l.stock_valuation_layer_id
         WHERE l.value_in_currency IS NOT NULL
        """,
    )
    _logger.info("Se respaldaron %s capas", backed_up)
