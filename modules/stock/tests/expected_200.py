# Test declarativo de la migración 19->20 de los lotes de traslados.
#
# 19.0: el menú de Lotes sale de stock_picking_batch, y lo ve cualquier usuario de Inventario.
# 20.0: stock_picking_batch se fusiona en stock, y el menú pide stock.group_stock_picking_batch.
#
# Lo activa modules/stock/20.0.0.0/post-migration.py en las bases que tenían el módulo,
# según el respaldo de scripts/pre_odoo/190_200/030-backup_stock_picking_batch_installed.py.

EXPECTED = {
    "res.groups": {
        # Rama con lotes en 19: el grupo tiene que quedar implícito de los usuarios internos,
        # como cuando se tilda la opción en Ajustes. Si viene [], quien usaba lotes se queda
        # sin el menú después del pase.
        ref("stock.group_stock_picking_batch"): {
            "implied_by_ids": [ref("base.group_user")],
        },
    },
}
