import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Las devoluciones agrupadas por el traslado del que salieron, según el vínculo a
# nivel movimiento. `origins > 1` marca las que mezclan líneas de varias entregas.
_RETURN_SOURCE = SQL(
    """
      SELECT m.picking_id,
             MIN(om.picking_id) AS origin_picking_id,
             COUNT(DISTINCT om.picking_id) AS origins
        FROM stock_move m
        JOIN stock_move om ON om.id = m.origin_returned_move_id
       WHERE m.picking_id IS NOT NULL
         AND om.picking_id IS NOT NULL
    GROUP BY m.picking_id
    """
)


def migrate(cr, version):
    """Reconstruye el vínculo entre una devolución y la entrega de la que salió.

    `stock.picking.return_id` existe desde la 17.0 y el upgrade oficial no lo
    completa: toda devolución que viene de una versión anterior queda sin el
    vínculo, y con él se pierde el botón "Devoluciones" de la entrega. El vínculo
    a nivel movimiento (`origin_returned_move_id`) sí sobrevive al pase, así que
    la cabecera se rehace desde ahí.

    Va en `always/` porque también repara, en su próximo salto, las bases que ya
    pasaron a 17 o 18 sin el dato.
    """
    _logger.info("Running 'restore_picking_return_link.py' script for version %s", version)

    if not util.column_exists(cr, "stock_picking", "return_id"):
        return

    cr.execute(
        SQL(
            """
            UPDATE stock_picking sp
               SET return_id = src.origin_picking_id
              FROM (%s) src
             WHERE sp.id = src.picking_id
               AND src.origins = 1
               AND sp.return_id IS NULL
            """,
            _RETURN_SOURCE,
        )
    )
    _logger.info("Restored the return link on %s transfers", cr.rowcount)

    cr.execute(
        SQL(
            """
            SELECT COUNT(*)
              FROM (%s) src
              JOIN stock_picking sp ON sp.id = src.picking_id
             WHERE src.origins > 1
               AND sp.return_id IS NULL
            """,
            _RETURN_SOURCE,
        )
    )
    skipped = cr.fetchone()[0]
    if skipped:
        _logger.warning(
            "%s devoluciones quedaron sin vínculo: sus líneas vienen de más de un traslado "
            "y no hay un único origen para apuntar.",
            skipped,
        )
