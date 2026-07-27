import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Moves de la propia OF: componentes (raw_material_production_id) y producto
# terminado (production_id). Tienen FK directa, el grupo sale sin ambigüedad.
_QUERY_RAW_MOVES = """
    UPDATE stock_move sm
       SET production_group_id = mp.production_group_id
      FROM mrp_production mp
     WHERE mp.id = sm.raw_material_production_id
       AND sm.production_group_id IS NULL
       AND mp.production_group_id IS NOT NULL
       AND {parallel_filter}
"""

_QUERY_FINISHED_MOVES = """
    UPDATE stock_move sm
       SET production_group_id = mp.production_group_id
      FROM mrp_production mp
     WHERE mp.id = sm.production_id
       AND sm.production_group_id IS NULL
       AND mp.production_group_id IS NOT NULL
       AND {parallel_filter}
"""

# Moves sin FK a la OF: el pick de componentes de fabricación en 2/3 pasos (PC) y
# el store-after-manufacturing (SAM). Se resuelven por la stock.reference que
# comparten con la OF, que la migración sí dejó bien armada.
# El HAVING descarta las referencias que resuelven a más de un grupo: en esos
# casos no hay un ganador obvio y preferimos no adivinar (se loguean aparte).
_QUERY_REFERENCE_MOVES = """
    WITH ref_group AS (
        SELECT rel.reference_id,
               min(mp.production_group_id) AS production_group_id
          FROM stock_reference_production_rel rel
          JOIN mrp_production mp ON mp.id = rel.production_id
         WHERE mp.production_group_id IS NOT NULL
         GROUP BY rel.reference_id
        HAVING count(DISTINCT mp.production_group_id) = 1
    )
    UPDATE stock_move sm
       SET production_group_id = rg.production_group_id
      FROM stock_reference_move_rel smr
      JOIN ref_group rg ON rg.reference_id = smr.reference_id
     WHERE sm.id = smr.move_id
       AND sm.production_group_id IS NULL
       AND {parallel_filter}
"""

# Referencias que quedan sin reparar por resolver a más de un grupo.
_QUERY_AMBIGUOUS = """
    SELECT count(*)
      FROM (
            SELECT rel.reference_id
              FROM stock_reference_production_rel rel
              JOIN mrp_production mp ON mp.id = rel.production_id
             WHERE mp.production_group_id IS NOT NULL
             GROUP BY rel.reference_id
            HAVING count(DISTINCT mp.production_group_id) > 1
           ) amb
"""


def migrate(cr, version):
    """
    Backfill de `stock_move.production_group_id` en las OF migradas desde v18.

    En v18 el vínculo OF <-> traslado vivía en `procurement.group`. La v19 lo
    reemplazó por `stock.reference` + `mrp.production.group`, y los dos smart
    buttons pasaron a computarse contra `stock_move.production_group_id`:

    - `mrp.production.picking_ids` busca los `stock.move` cuyo
      `production_group_id` coincide con el de la OF (mrp/models/mrp_production.py).
    - `stock.picking.production_ids` navega `move_ids.production_group_id.production_ids`
      (mrp/models/stock_picking.py).

    La migración a v19 crea el `mrp.production.group`, lo asigna a la OF y arma la
    `stock.reference` completa (con sus productions, moves y pickings), pero no
    propaga el grupo a los `stock.move` — que es lo que sí hace `mrp.production.create`
    en el flujo normal. Resultado: en las OF migradas los dos smart buttons quedan
    vacíos y se pierde la navegación OF <-> traslado. Solo el síntoma es visible en
    fabricación multi-paso (donde existe el pick de componentes), pero el dato queda
    igual de incompleto en 1 paso.

    No alcanza con recomputar: ambos campos son computed no almacenados, ya devuelven
    vacío en vivo. Hay que escribir el dato faltante.

    Referencia: ticket #123590 (baratecsolar, 19.0).
    """
    if not util.column_exists(cr, "stock_move", "production_group_id"):
        _logger.warning(
            "stock_move.production_group_id no existe; se omite el backfill de production_group_id"
        )
        return

    _logger.info("Backfill de stock_move.production_group_id en OF migradas")

    # Idempotente: solo toca moves con production_group_id NULL.
    raw_count = util.explode_execute(cr, _QUERY_RAW_MOVES, table="stock_move", alias="sm")
    finished_count = util.explode_execute(cr, _QUERY_FINISHED_MOVES, table="stock_move", alias="sm")
    _logger.info(
        "Moves de la OF actualizados: %d componentes, %d producto terminado",
        raw_count,
        finished_count,
    )

    if util.table_exists(cr, "stock_reference_move_rel"):
        reference_count = util.explode_execute(
            cr, _QUERY_REFERENCE_MOVES, table="stock_move", alias="sm"
        )
        _logger.info(
            "Moves de traslados vinculados por stock.reference actualizados: %d", reference_count
        )

        cr.execute(_QUERY_AMBIGUOUS)
        ambiguous_count = cr.fetchone()[0]
        if ambiguous_count:
            _logger.warning(
                "%d stock.reference resuelven a más de un production group; sus moves de"
                " traslado quedan sin vincular y hay que revisarlos a mano",
                ambiguous_count,
            )
    else:
        _logger.warning(
            "stock_reference_move_rel no existe; los traslados de fabricación multi-paso"
            " quedan sin vincular"
        )
