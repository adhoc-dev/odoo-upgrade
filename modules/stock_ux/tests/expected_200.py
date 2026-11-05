# Test declarativo de stock_ux/20.0.1.0.0/pre-migration.py.
#
# La transformacion: util.remove_field sobre los campos que stock_ux deja de
# definir en 20 (stock.move.picking_partner_id, stock.move.picking_dest_id y
# stock.warehouse.orderpoint.qty_multiple).
#
#   favorito, campo related en el dominio   -> pasa al camino del related
#   favorito, campo guardado en un AND      -> la condicion queda verdadera
#   group by y orden sobre el campo         -> se van
#   exportacion con el campo                -> se va esa linea
#   exportacion con el campo en un camino   -> se va esa linea
#   picking_partner_id de stock.move.line   -> no se toca (preservacion)
#
# Los siembra tests/pre_odu/stock_ux/190_200/010-favorites_and_exports_on_removed_fields.py.
#
# Que las lineas de exportacion sacadas ya no esten no se puede declarar: un
# registro ausente es FAIL siempre. Se declara la lista de lineas que le queda
# a cada exportacion.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "ir.filters": {
        # picking_partner_id es related de picking_id.partner_id: el dominio
        # pasa a usar ese camino y sigue buscando lo mismo. El group by y el
        # orden sobre el campo se van. Si el dominio sigue con el campo, el
        # script no corrio.
        ref("upgrade_prepare_demo.filter_stock_move_picking_partner"): {
            "domain": "[('picking_id.partner_id', '!=', False)]",
            "context": "{'group_by': []}",
            "sort": '["date"]',
            "active": True,
        },
        # qty_multiple era un campo guardado sin reemplazo: en un AND, su
        # condicion queda siempre verdadera y la otra sigue.
        ref("upgrade_prepare_demo.filter_orderpoint_qty_multiple"): {
            "domain": "['&', (1, '=', 1), ('product_min_qty', '>', 0)]",
            "context": "{'group_by': []}",
            "active": True,
        },
        # Preservacion: el campo de core en stock.move.line. Si cambia, el
        # script saco el campo de un modelo que no era.
        ref("upgrade_prepare_demo.filter_stock_move_line_picking_partner"): {
            "domain": "[('picking_partner_id', '!=', False)]",
            "context": "{'group_by': ['picking_partner_id']}",
            "active": True,
        },
    },
    "ir.exports": {
        # Solo queda product_id. Si quedan las lineas de picking_partner_id o
        # picking_dest_id, la exportacion falla al abrirla.
        ref("upgrade_prepare_demo.export_stock_move"): {
            "export_fields": [ref("upgrade_prepare_demo.export_stock_move_product")],
        },
        ref("upgrade_prepare_demo.export_orderpoint"): {
            "export_fields": [ref("upgrade_prepare_demo.export_orderpoint_product")],
        },
        # El campo llegaba por move_ids/picking_partner_id desde la
        # transferencia: si queda, el script solo miro las exportaciones de
        # stock.move.
        ref("upgrade_prepare_demo.export_stock_picking"): {
            "export_fields": [ref("upgrade_prepare_demo.export_stock_picking_name")],
        },
        # Preservacion: si la linea se fue, el script saco el campo de core.
        ref("upgrade_prepare_demo.export_stock_move_line"): {
            "export_fields": [ref("upgrade_prepare_demo.export_stock_move_line_picking_partner")],
        },
    },
}
