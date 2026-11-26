import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/180_190/060-backup_currency_valuation_layers.py, del otro lado del pase.
BACKUP_TABLE = "stock_valuation_layer_currency_bu"
# Las columnas con las que el pre-odoo separa las capas de cada movimiento. Un respaldo
# anterior al que las guarda no las tiene, y los dos lados del pase no corren a la vez.
BACKUP_COLUMNS = ("landed_cost_id", "parent_layer_id")


# Capas de 18 que el pase pudo haber sumado al `value` de un movimiento, en el orden en que
# se prueban. Medido en una base real: casi siempre solo la capa propia, sin los costos en
# destino; con diferencia de precio, a veces con ella y a veces sin.
_MOVE_LAYER_SETS = SQL(
    """
    (VALUES (1, false, false),
            (2, true, false),
            (3, false, true),
            (4, true, true)) AS c(prio, with_pdiff, with_lc)
    """
)

# Las capas de cada movimiento, separadas en la propia, las diferencias de precio y los
# costos en destino.
_MOVE_PARTS = """
    SELECT move_id,
           SUM(value) FILTER (WHERE kind = 'own') AS own_value,
           SUM(value_in_currency) FILTER (WHERE kind = 'own') AS own_currency,
           SUM(value) FILTER (WHERE kind = 'pdiff') AS pdiff_value,
           SUM(value_in_currency) FILTER (WHERE kind = 'pdiff') AS pdiff_currency,
           SUM(value) FILTER (WHERE kind = 'lc') AS lc_value,
           SUM(value_in_currency) FILTER (WHERE kind = 'lc') AS lc_currency
      FROM (SELECT move_id, value, value_in_currency,
                   CASE WHEN landed_cost_id IS NOT NULL THEN 'lc'
                        WHEN parent_layer_id IS NOT NULL THEN 'pdiff'
                        ELSE 'own' END AS kind
              FROM %(backup)s
             WHERE move_id IS NOT NULL) b
     GROUP BY move_id
"""


def _restore_moves(cr):
    """El valor en moneda de cada movimiento, con las mismas capas que el pase sumó en pesos.

    Los pesos que deja el pase no se tocan: el valor en moneda se arma igual. Para cada
    movimiento se busca qué capas de 18 suman su `stock_move.value` (la propia, con o sin
    diferencia de precio y costos en destino) y se carga la suma en moneda de esas mismas
    capas. Así el tipo de cambio implícito es el de la capa, y si el pase cambia su regla,
    esto lo sigue. Los costos en destino que el pase no sumó quedan en moneda en
    `stock_valuation_adjustment_lines`. En 19 el valor de un movimiento va siempre en
    positivo, también en las salidas, así que va el absoluto.
    """
    chosen = SQL(
        """
        WITH parts AS (""" + _MOVE_PARTS + """),
        candidates AS (
            SELECT p.move_id, c.prio,
                   ABS(COALESCE(p.own_value, 0)
                       + CASE WHEN c.with_pdiff THEN COALESCE(p.pdiff_value, 0) ELSE 0 END
                       + CASE WHEN c.with_lc THEN COALESCE(p.lc_value, 0) ELSE 0 END) AS value,
                   ABS(COALESCE(p.own_currency, 0)
                       + CASE WHEN c.with_pdiff THEN COALESCE(p.pdiff_currency, 0) ELSE 0 END
                       + CASE WHEN c.with_lc THEN COALESCE(p.lc_currency, 0) ELSE 0 END) AS value_in_currency
              FROM parts p
             CROSS JOIN %(layer_sets)s
        ),
        chosen AS (
            SELECT DISTINCT ON (c.move_id) c.move_id, c.value_in_currency
              FROM candidates c
              JOIN stock_move m ON m.id = c.move_id
             WHERE ABS(COALESCE(m.value, 0) - c.value) <= 0.01
             ORDER BY c.move_id, c.prio
        )
        """,
        backup=SQL.identifier(BACKUP_TABLE),
        layer_sets=_MOVE_LAYER_SETS,
    )
    cr.execute(
        SQL(
            """
            %(chosen)s
            UPDATE stock_move m
               SET value_in_currency = ch.value_in_currency
              FROM chosen ch
             WHERE m.id = ch.move_id
               AND ch.value_in_currency <> 0
               AND m.value_in_currency IS DISTINCT FROM ch.value_in_currency
            """,
            chosen=chosen,
        )
    )
    restored = cr.rowcount
    cr.execute(
        SQL(
            """
            %(chosen)s
            SELECT p.move_id
              FROM (SELECT DISTINCT move_id FROM %(backup)s WHERE move_id IS NOT NULL) p
              JOIN stock_move m ON m.id = p.move_id
             WHERE NOT EXISTS (SELECT 1 FROM chosen ch WHERE ch.move_id = p.move_id)
             ORDER BY p.move_id
            """,
            chosen=chosen,
            backup=SQL.identifier(BACKUP_TABLE),
        )
    )
    unmatched = [move_id for (move_id,) in cr.fetchall()]
    return restored, unmatched


def _check_landed_costs(cr):
    """Compara la cotización de los costos en destino contra las capas de 18.

    En 19 el valor en moneda vive en
    `stock_valuation_adjustment_lines.additional_landed_cost_in_currency`, que el módulo
    calcula en el `-u` con la cotización del costo en destino. Se compara la cotización
    (moneda sobre pesos) y no el importe: con stock ya vendido, la capa de 18 lleva solo la
    parte del stock que quedaba y la línea de 19, el costo entero. No se escribe: solo se
    avisa qué costos en destino no coinciden, por movimiento.
    """
    if not util.column_exists(cr, "stock_valuation_adjustment_lines", "additional_landed_cost_in_currency"):
        _logger.warning("Sin additional_landed_cost_in_currency: no se compararon los costos en destino")
        return []
    cr.execute(
        SQL(
            """
            WITH layers AS (
                SELECT landed_cost_id, move_id,
                       SUM(value) AS value, SUM(value_in_currency) AS value_in_currency
                  FROM %(backup)s
                 WHERE landed_cost_id IS NOT NULL AND move_id IS NOT NULL
                 GROUP BY landed_cost_id, move_id
                HAVING SUM(value) <> 0
            ),
            lines AS (
                SELECT cost_id, move_id, COUNT(*) AS line_count,
                       SUM(additional_landed_cost) AS value,
                       SUM(additional_landed_cost_in_currency) AS value_in_currency
                  FROM stock_valuation_adjustment_lines
                 GROUP BY cost_id, move_id
            )
            SELECT l.landed_cost_id, l.move_id,
                   ROUND(a.value * l.value_in_currency / l.value, 2) AS expected,
                   a.value_in_currency
              FROM layers l
              LEFT JOIN lines a ON a.cost_id = l.landed_cost_id AND a.move_id = l.move_id
             WHERE a.cost_id IS NULL
                -- each line is rounded on its own, so allow one cent per line
                OR ABS(a.value * l.value_in_currency / l.value - a.value_in_currency) > 0.01 * a.line_count
             ORDER BY l.landed_cost_id, l.move_id
            """,
            backup=SQL.identifier(BACKUP_TABLE),
        )
    )
    return cr.fetchall()


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

    missing = [column for column in BACKUP_COLUMNS if not util.column_exists(cr, BACKUP_TABLE, column)]
    if missing:
        # El respaldo lo hizo un pre-odoo anterior a este script: sin esas columnas no se sabe
        # qué capas suma el pase a cada movimiento, y restaurar a medias sería peor.
        _logger.warning(
            "%s no trae %s: lo hizo un pre-odoo anterior. El valor en moneda queda vacío; "
            "para cargarlo hay que rehacer el pase desde el pre-odoo.",
            BACKUP_TABLE,
            ", ".join(missing),
        )
        return

    moves, unmatched = _restore_moves(cr)
    _logger.info("Valor en moneda cargado en %s movimientos", moves)
    if unmatched:
        # Ninguna combinación de sus capas de 18 da el valor en pesos que dejó el pase: el
        # valor en moneda queda sin cargar y hay que mirarlo a mano.
        _logger.warning(
            "%s movimientos sin valor en moneda: sus capas no suman el valor que dejó el pase. Primeros: %s",
            len(unmatched),
            unmatched[:20],
        )

    lc_diffs = _check_landed_costs(cr)
    if lc_diffs:
        _logger.warning(
            "%s costos en destino con otra cotización que en 18 (costo, movimiento, esperado, 19). Primeros: %s",
            len(lc_diffs),
            lc_diffs[:20],
        )

    restored, revaluations = _restore_revaluations(cr)
    _logger.info("Valor en moneda cargado en %s de %s revalorizaciones", restored, revaluations)
    if restored < revaluations:
        # Una revalorización sin pareja, o sobre un producto sin stock en ese momento: su
        # product.value queda sin valor en moneda y hay que mirarlo a mano.
        _logger.warning(
            "%s revalorizaciones quedaron sin valor en moneda: no se encontró su product.value",
            revaluations - restored,
        )
