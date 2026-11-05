import logging

_logger = logging.getLogger(__name__)

# Casos de stock_ux/20.0.1.0.0/pre-migration.py, que al pasar a 20 saca los
# campos que stock_ux deja de definir: stock.move.picking_partner_id,
# stock.move.picking_dest_id y stock.warehouse.orderpoint.qty_multiple. Los
# verifica stock_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: ninguna data de prueba trae favoritos ni
# exportaciones guardadas sobre estos campos. En un cliente son los que arma
# el usuario desde la lista de movimientos o de reglas de reabastecimiento.
#
# En 19 los campos existen, asi que se cargan con el ORM.

PREFIX = "upgrade_prepare_demo."

FILTERS = {
    # Related: el dominio pasa a usar el camino del related, y el group by y el
    # orden sobre el campo se van.
    "filter_stock_move_picking_partner": (
        "stock.move",
        "[('picking_partner_id', '!=', False)]",
        "{'group_by': ['picking_partner_id']}",
        '["picking_partner_id desc", "date"]',
    ),
    # Campo guardado: en un AND, la condicion queda siempre verdadera y la otra
    # sigue.
    "filter_orderpoint_qty_multiple": (
        "stock.warehouse.orderpoint",
        "[('qty_multiple', '>', 1), ('product_min_qty', '>', 0)]",
        "{'group_by': ['qty_multiple']}",
        "[]",
    ),
    # Preservacion: el picking_partner_id de stock.move.line es de core y sigue
    # en 20.
    "filter_stock_move_line_picking_partner": (
        "stock.move.line",
        "[('picking_partner_id', '!=', False)]",
        "{'group_by': ['picking_partner_id']}",
        "[]",
    ),
}

EXPORTS = {
    # Los dos campos de stock.move, junto a uno que sigue.
    "export_stock_move": (
        "stock.move",
        {
            "export_stock_move_product": "product_id",
            "export_stock_move_picking_partner": "picking_partner_id",
            "export_stock_move_picking_dest": "picking_dest_id",
        },
    ),
    "export_orderpoint": (
        "stock.warehouse.orderpoint",
        {
            "export_orderpoint_product": "product_id",
            "export_orderpoint_qty_multiple": "qty_multiple",
        },
    ),
    # El campo llega por un camino, desde otro modelo.
    "export_stock_picking": (
        "stock.picking",
        {
            "export_stock_picking_name": "name",
            "export_stock_picking_move_partner": "move_ids/picking_partner_id",
        },
    ),
    # Preservacion: el campo de core en stock.move.line.
    "export_stock_move_line": (
        "stock.move.line",
        {
            "export_stock_move_line_picking_partner": "picking_partner_id",
        },
    ),
}


def migrate(env):
    if (
        "picking_partner_id" not in env["stock.move"]._fields
        or "qty_multiple" not in env["stock.warehouse.orderpoint"]._fields
    ):
        _logger.info("stock_ux is not installed - not seeding it")
        return

    for name, (model, domain, context, sort) in FILTERS.items():
        env["ir.filters"]._load_records(
            [
                {
                    "xml_id": PREFIX + name,
                    "values": {
                        "name": "Upgrade: %s" % name,
                        "model_id": model,
                        "domain": domain,
                        "context": context,
                        "sort": sort,
                        "active": True,
                    },
                    "noupdate": True,
                }
            ]
        )

    for name, (model, lines) in EXPORTS.items():
        export = env["ir.exports"]._load_records(
            [
                {
                    "xml_id": PREFIX + name,
                    "values": {"name": "Upgrade: %s" % name, "resource": model},
                    "noupdate": True,
                }
            ]
        )
        env["ir.exports.line"]._load_records(
            [
                {
                    "xml_id": PREFIX + line_name,
                    "values": {"name": path, "export_id": export.id},
                    "noupdate": True,
                }
                for line_name, path in lines.items()
            ]
        )
