import logging

_logger = logging.getLogger(__name__)

# Lineas de ventas confirmadas con el delivery_status guardado en 'no' aunque
# tengan algo para entregar: es lo que quedo en las bases donde el modulo se
# instalo con ventas ya cargadas (el campo es stored con default 'no'). Lo
# verifica sale_stock_ux/tests/expected_200.py despues del -u, contra
# modules/sale_stock_ux/20.0.1.0.0/post-migration.py.
#
#   sol_stale_to_deliver: 10 pedidas, nada entregado, guardada en 'no'
#   sol_stale_forced_no:  igual, pero la venta forzada a "Nada para entregar"
#                         (preservacion: el forzado manda)
CASES = [
    ("so_stale_to_deliver", "sol_stale_to_deliver", False),
    ("so_stale_forced_no", "sol_stale_forced_no", "no"),
]


def migrate(env):
    if (
        "sale.order.line" not in env
        or "delivery_status" not in env["sale.order.line"]._fields
    ):
        _logger.info("sale_stock_ux no esta en esta base — no se siembra nada")
        return
    product = env["product.product"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.product_stale_delivery_status",
                "values": {
                    "name": "Stale delivery status",
                    "type": "consu",
                    "is_storable": True,
                },
                "noupdate": True,
            }
        ]
    )
    partner = env["res.partner"].search([], limit=1)
    for order_name, line_name, forced in CASES:
        order = env["sale.order"]._load_records(
            [
                {
                    "xml_id": f"upgrade_prepare_demo.{order_name}",
                    "values": {"partner_id": partner.id},
                    "noupdate": True,
                }
            ]
        )
        line = env["sale.order.line"]._load_records(
            [
                {
                    "xml_id": f"upgrade_prepare_demo.{line_name}",
                    "values": {
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_uom_qty": 10,
                    },
                    "noupdate": True,
                }
            ]
        )
        if order.state == "draft":
            order.action_confirm()
        if forced:
            order.force_delivery_status = forced
        env.flush_all()
        # El valor que dejo la instalacion del modulo, no el que calcula hoy.
        env.cr.execute(
            "UPDATE sale_order_line SET delivery_status = 'no' WHERE id = %s", [line.id]
        )
    env.invalidate_all()
    _logger.info("Seeded %s sale order lines with a stale delivery status", len(CASES))
