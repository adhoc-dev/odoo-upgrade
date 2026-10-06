import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/180_190/050-backup_move_packaging.py, del otro lado del pase.
BACKUP_TABLE = "stock_move_packaging_bu"


def _packaging_uoms(env):
    """{(UdM de referencia, contenido): UdM} — con qué UdM representa la 19 cada empaque.

    El pase deduplica por contenido y referencia, no por nombre: dos empaques de 20 kg que se
    llamaban distinto quedan en una sola UdM, y el nombre que sobrevive es el de uno de ellos
    o uno generado ("Pack 4.00"). Por eso el contenido es lo que identifica. El contenido va
    redondeado a 6 decimales porque es clave de diccionario; el pase lo copia tal cual, así
    que la igualdad es exacta en la práctica.
    """
    index = {}
    uoms = env["uom.uom"].with_context(active_test=False).search([("relative_uom_id", "!=", False)])
    for uom in uoms.sorted(key=lambda u: (not u.active, u.id)):
        key = (uom.relative_uom_id.id, round(uom.relative_factor, 6))
        index[key] = index.get(key, env["uom.uom"]) | uom
    return index


def _odoo_uom_ids(cr):
    """Las UdM que trae Odoo, que son las que tienen xmlid.

    Un empaque de 12 unidades también calza con la docena, y las UdM de Odoo tienen los ids
    más bajos: sin esto, un empaque que no gana por nombre ni por el vínculo al producto se
    lo llevaría la docena en vez de la UdM que creó el pase.
    """
    cr.execute("SELECT res_id FROM ir_model_data WHERE model = 'uom.uom'")
    return {row[0] for row in cr.fetchall()}


def _find_uom(product, name, qty, index, odoo_uom_ids):
    """La UdM del empaque: la que ya está en el producto, si no la del mismo nombre."""
    # float() porque product_packaging.qty era numeric y llega como Decimal, que no compara
    # con el float de relative_factor cuando el contenido no es exacto en binario.
    candidates = index.get((product.uom_id.id, round(float(qty), 6)))
    if not candidates:
        return None
    linked = candidates & product.uom_ids
    if linked:
        return linked[:1]
    by_name = candidates.filtered(lambda u: (u.name or "").strip().lower() == (name or "").strip().lower())
    if by_name:
        return by_name[:1]
    return (candidates.filtered(lambda u: u.id not in odoo_uom_ids) or candidates)[:1]


def migrate(cr, version):
    """Restaura en los movimientos el empaque que el pase deja en el camino.

    El pase convierte cada product.packaging en una UdM del producto, pero no baja el dato a
    los movimientos: `stock_move.packaging_uom_id` se computa de `product_uom` y queda en la
    UdM del producto, así que el remito muestra "Unidades" donde 18 mostraba "Bulto x12".

    `packaging_uom_id` es stored computed sin inverse: se escribe por SQL. La cantidad sí se
    recomputa por ORM — la conversión redondea con la precisión de la UdM y replicar
    `float_round` en SQL da de más justo en el caso limpio (240/12 en float).

    Va en end-migration porque el valor cruza módulos: con sale_stock instalado el compute
    nativo lo toma de la UdM de la línea de venta, así que esto tiene que ser la última
    palabra. Idempotente: solo toca lo desalineado y se puede volver a correr.
    """
    if not util.table_exists(cr, BACKUP_TABLE):
        # No es "no hay empaques": es que nadie los respaldó.
        _logger.warning("No existe %s: los movimientos quedan sin empaque. ¿Corrió el pre-odoo?", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            SELECT product_id, packaging_name, packaging_qty, array_agg(id)
              FROM %s
             GROUP BY product_id, packaging_name, packaging_qty
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    rows = cr.fetchall()
    if not rows:
        _logger.info("%s está vacía: la base no usaba empaques", BACKUP_TABLE)
        return

    env = util.env(cr)
    index = _packaging_uoms(env)
    odoo_uom_ids = _odoo_uom_ids(cr)
    products = {p.id: p for p in env["product.product"].browse({row[0] for row in rows}).exists()}

    matched_ids = []
    changed = 0
    for product_id, name, qty, move_ids in rows:
        product = products.get(product_id)
        uom = _find_uom(product, name, qty, index, odoo_uom_ids) if product else None
        if not uom:
            # Sin UdM de ese contenido no hay nada que poner, y hay que mirarlo: o el pase no
            # la creó, o la UdM del producto cambió y el contenido ya no se expresa igual.
            _logger.warning(
                "Sin UdM para el empaque %r (contenido %s) del producto %s: %s movimientos quedan sin empaque",
                name,
                qty,
                product_id,
                len(move_ids),
            )
            continue
        cr.execute(
            """
            UPDATE stock_move
               SET packaging_uom_id = %s
             WHERE id = ANY(%s)
               AND packaging_uom_id IS DISTINCT FROM %s
            """,
            (uom.id, move_ids, uom.id),
        )
        changed += cr.rowcount
        matched_ids.extend(move_ids)

    if matched_ids:
        util.recompute_fields(cr, "stock.move", ["packaging_uom_qty"], matched_ids)
    _logger.info("Empaque restaurado en %s movimientos (%s cambiaron de UdM)", len(matched_ids), changed)
