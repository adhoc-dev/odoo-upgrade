import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/180_190/060-backup_currency_valuation_layers.py, del otro lado del pase.
BACKUP_TABLE = "stock_valuation_layer_currency_bu"


def _restore_moves(cr):
    """El valor en moneda de cada movimiento: la suma de sus capas de 18.

    Es la misma regla con la que el pase arma `stock_move.value`: la capa del movimiento,
    sus costos en destino y las diferencias de precio que colgaban de ella. En 19 el valor
    de un movimiento va siempre en positivo, también en las salidas, así que va el absoluto.
    """
    cr.execute(
        SQL(
            """
            UPDATE stock_move m
               SET value_in_currency = s.value_in_currency
              FROM (SELECT move_id, ABS(SUM(value_in_currency)) AS value_in_currency
                      FROM %(backup)s
                     WHERE move_id IS NOT NULL
                     GROUP BY move_id
                    HAVING SUM(value_in_currency) <> 0) s
             WHERE m.id = s.move_id
               AND m.value_in_currency IS DISTINCT FROM s.value_in_currency
            """,
            backup=SQL.identifier(BACKUP_TABLE),
        )
    )
    return cr.rowcount


def _restore_revaluations(cr):
    """El valor en moneda de las revalorizaciones, que el pase convirtió en product.value.

    En 19 una revalorización guarda el costo unitario que quedó, no el importe agregado como
    la capa de 18. Se reconstruye con el costo promedio en moneda de ese momento: valor
    acumulado sobre cantidad acumulada del producto, después de la capa (el valor nuevo) y
    antes (el anterior). El pase no deja vínculo entre la capa y el product.value: se
    emparejan por producto, lote y descripción, en orden de fecha.
    """
    cr.execute(
        SQL(
            """
            WITH running AS (
                SELECT company_id, product_id, lot_id, description, is_revaluation,
                       value_in_currency,
                       SUM(value_in_currency) OVER w AS cum_value,
                       SUM(quantity) OVER w AS cum_qty,
                       ROW_NUMBER() OVER (
                           PARTITION BY company_id, product_id, lot_id, description, is_revaluation
                           ORDER BY create_date, id
                       ) AS seq
                  FROM %(backup)s
                WINDOW w AS (PARTITION BY company_id, product_id ORDER BY create_date, id)
            ),
            revaluations AS (
                SELECT * FROM running WHERE is_revaluation AND cum_qty <> 0
            ),
            product_values AS (
                SELECT id, company_id, product_id, lot_id, description,
                       ROW_NUMBER() OVER (
                           PARTITION BY company_id, product_id, lot_id, description
                           ORDER BY date, id
                       ) AS seq
                  FROM product_value
                 WHERE move_id IS NULL
            )
            UPDATE product_value t
               SET value_in_currency = r.cum_value / r.cum_qty,
                   previous_value_in_currency = (r.cum_value - r.value_in_currency) / r.cum_qty
              FROM revaluations r
              JOIN product_values pv
                ON pv.company_id = r.company_id
               AND pv.product_id = r.product_id
               AND pv.lot_id IS NOT DISTINCT FROM r.lot_id
               AND pv.description = r.description
               AND pv.seq = r.seq
             WHERE t.id = pv.id
            """,
            backup=SQL.identifier(BACKUP_TABLE),
        )
    )
    restored = cr.rowcount
    cr.execute(
        SQL(
            "SELECT count(*) FROM %(backup)s WHERE is_revaluation",
            backup=SQL.identifier(BACKUP_TABLE),
        )
    )
    return restored, cr.fetchone()[0]


def migrate(cr, version):
    """Carga en 19 el valor en moneda que en 18 vivía en las capas de valuación.

    El pase borra stock.valuation.layer: el valor en moneda llega solo por el respaldo del
    pre-odoo. Va en post-migration porque las columnas en moneda las crea este módulo en el
    `-u`. Idempotente: un `-u` repetido deja los mismos valores.
    """
    if not util.table_exists(cr, BACKUP_TABLE):
        # No es "no había valores": es que nadie los respaldó.
        _logger.warning("No existe %s: el valor en moneda queda vacío. ¿Corrió el pre-odoo?", BACKUP_TABLE)
        return

    moves = _restore_moves(cr)
    _logger.info("Valor en moneda cargado en %s movimientos", moves)

    restored, revaluations = _restore_revaluations(cr)
    _logger.info("Valor en moneda cargado en %s de %s revalorizaciones", restored, revaluations)
    if restored < revaluations:
        # Una revalorización sin pareja, o sobre un producto sin stock en ese momento: su
        # product.value queda sin valor en moneda y hay que mirarlo a mano.
        _logger.warning(
            "%s revalorizaciones quedaron sin valor en moneda: no se encontró su product.value",
            revaluations - restored,
        )
