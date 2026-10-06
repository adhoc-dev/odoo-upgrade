import logging

_logger = logging.getLogger(__name__)

# Casos del empaque de los movimientos (18 -> 19). En 18 el empaque es un product.packaging
# que el movimiento apunta con product_packaging_id; en 19 es una UdM del producto y el
# movimiento la lleva en packaging_uom_id. Los verifican los tests declarativos de este repo
# (modules/stock/tests/expected_190.py) por packaging_uom_qty: la cantidad en empaques es el
# único valor escalar que distingue si el empaque llegó, porque la UdM que crea el pase no
# tiene xmlid contra el que declarar un ref().
#
# _load_records (nativo de BaseModel) registra los xmlids estables en ir.model.data bajo el
# modulo virtual 'upgrade_prepare_demo' y es idempotente: re-correr el script no duplica
# registros.
PACKAGING_QTY = 12.0
# 240 unidades = 20 bultos de 12: ni el total ni la cantidad en empaques se parecen, así que
# un empaque perdido no puede pasar por bueno.
QTY_WITH_PACKAGING = 240.0
QTY_WITHOUT_PACKAGING = 7.0


def migrate(env):
    if "product.packaging" not in env or "product_packaging_id" not in env["stock.move"]._fields:
        _logger.info("Esta base no tiene empaques de 18 — no se siembra nada")
        return

    uom_unit = env.ref("uom.product_uom_unit")
    env["product.product"]._load_records([{
        "xml_id": "upgrade_prepare_demo.product_move_packaging",
        "values": {"name": "Producto con empaque (upgrade test)", "uom_id": uom_unit.id},
        "noupdate": True,
    }])
    product = env.ref("upgrade_prepare_demo.product_move_packaging")

    env["product.packaging"]._load_records([{
        "xml_id": "upgrade_prepare_demo.packaging_bulto_12",
        "values": {"name": "Bulto x 12 unidades", "product_id": product.id, "qty": PACKAGING_QTY},
        "noupdate": True,
    }])
    packaging = env.ref("upgrade_prepare_demo.packaging_bulto_12")

    location = env.ref("stock.stock_location_stock")
    location_dest = env.ref("stock.stock_location_customers")
    common = {
        "product_id": product.id,
        "product_uom": uom_unit.id,
        "location_id": location.id,
        "location_dest_id": location_dest.id,
    }
    env["stock.move"]._load_records([
        {
            "xml_id": "upgrade_prepare_demo.move_with_packaging",
            "values": dict(
                common,
                name="Movimiento con empaque (upgrade test)",
                product_uom_qty=QTY_WITH_PACKAGING,
                product_packaging_id=packaging.id,
            ),
            "noupdate": True,
        },
        {
            "xml_id": "upgrade_prepare_demo.move_without_packaging",
            "values": dict(
                common,
                name="Movimiento sin empaque (upgrade test)",
                product_uom_qty=QTY_WITHOUT_PACKAGING,
            ),
            "noupdate": True,
        },
    ])
    _logger.info("Seeded 2 stock moves for the packaging migration tests")
