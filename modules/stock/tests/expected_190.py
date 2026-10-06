# Test declarativo de la migración 18->19 del empaque de los movimientos.
#
# 18.0: stock.move.product_packaging_id -> product.packaging (modelo propio)
# 19.0: stock.move.packaging_uom_id -> uom.uom del producto (product.template.uom_ids)
#
# El pase crea las UdM pero no baja el dato a los movimientos, así que el remito pierde el
# empaque. Lo restaura modules/stock/19.0.0.0/end-migration.py desde el respaldo que deja
# scripts/pre_odoo/180_190/050-backup_move_packaging.py.
#
# Se verifica por `packaging_uom_qty` (la cantidad en empaques) y no por `packaging_uom_id`:
# la UdM que crea el pase no tiene xmlid contra el que declarar un ref(), y la cantidad
# depende de esa misma UdM, así que discrimina igual.
#
# Los registros llegan por xmlid desde la siembra de
# tests/pre_odu/stock/180_190/010-move_packaging_cases.py.

EXPECTED = {
    "stock.move": {
        # Rama con empaque: el movimiento salió con 240 unidades y un "Bulto x 12 unidades",
        # así que en 19 tiene que quedar en 20 bultos. Si acá viene 240, packaging_uom_id
        # quedó en la UdM del producto: el empaque no se mapeó y el remito imprime
        # "Unidades" en la columna del empaque.
        ref("upgrade_prepare_demo.move_with_packaging"): {
            "packaging_uom_qty": 20.0,
        },
        # Rama de preservación: el movimiento nunca tuvo empaque (7 unidades) y tiene que
        # seguir contándose en unidades. Verifica que el script no le invente un empaque a
        # los movimientos que no estaban en el respaldo — el falso positivo más probable,
        # porque el respaldo agrupa por producto y todos comparten el mismo.
        ref("upgrade_prepare_demo.move_without_packaging"): {
            "packaging_uom_qty": 7.0,
        },
    },
}
