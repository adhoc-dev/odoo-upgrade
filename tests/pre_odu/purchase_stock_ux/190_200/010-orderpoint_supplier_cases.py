import logging

_logger = logging.getLogger(__name__)

# Casos de purchase_stock_ux/20.0.1.0.0/pre-migration.py, que al pasar a 20 le
# saca el proveedor fijo a las reglas de reabastecimiento que creo OdooBot con
# disparador manual. Lo verifica purchase_stock_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la demo de 19 no trae reglas de reabastecimiento, y
# las que crea el informe de reabastecimiento no tienen xmlid.
#
# El creador de cada regla es lo que separa las ramas: este script corre en
# odoo shell como OdooBot, asi que las reglas "de una persona" se crean con el
# usuario admin. Cada regla va con su producto, porque producto, ubicacion y
# compania son unicos.
CASES = [
    # (sufijo, disparador, creada por una persona)
    ("odoobot_manual", "manual", False),
    ("person_manual", "manual", True),
    ("odoobot_auto", "auto", False),
]


def migrate(env):
    if "stock.warehouse.orderpoint" not in env or "supplier_id" not in env["stock.warehouse.orderpoint"]._fields:
        _logger.info("purchase_stock is not installed - not seeding it")
        return
    if not env["ir.module.module"].search_count([("name", "=", "purchase_stock_ux"), ("state", "=", "installed")]):
        _logger.info("purchase_stock_ux is not installed - not seeding it")
        return
    warehouse = env.ref("stock.warehouse0", raise_if_not_found=False)
    person = env.ref("base.user_admin", raise_if_not_found=False)
    if not warehouse or not person:
        # Sin el deposito o el admin de la demo no hay caso: lo dice el check como ref ausente
        _logger.info("stock.warehouse0 or base.user_admin is not in this database - not seeding it")
        return
    env["res.partner"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.op_supplier_vendor",
                "values": {"name": "Orderpoint supplier vendor"},
                "noupdate": True,
            }
        ]
    )
    vendor = env.ref("upgrade_prepare_demo.op_supplier_vendor")
    for suffix, trigger, by_person in CASES:
        env["product.product"]._load_records(
            [
                {
                    "xml_id": "upgrade_prepare_demo.op_supplier_product_%s" % suffix,
                    "values": {"name": "Orderpoint supplier %s" % suffix, "type": "consu", "is_storable": True},
                    "noupdate": True,
                }
            ]
        )
        product = env.ref("upgrade_prepare_demo.op_supplier_product_%s" % suffix)
        env["product.supplierinfo"]._load_records(
            [
                {
                    "xml_id": "upgrade_prepare_demo.op_supplier_info_%s" % suffix,
                    "values": {"partner_id": vendor.id, "product_tmpl_id": product.product_tmpl_id.id, "price": 10.0},
                    "noupdate": True,
                }
            ]
        )
        orderpoints = env["stock.warehouse.orderpoint"]
        if by_person:
            orderpoints = orderpoints.with_user(person)
        orderpoints._load_records(
            [
                {
                    "xml_id": "upgrade_prepare_demo.op_supplier_%s" % suffix,
                    "values": {
                        "product_id": product.id,
                        "location_id": warehouse.lot_stock_id.id,
                        "trigger": trigger,
                        "product_min_qty": 0.0,
                        "product_max_qty": 0.0,
                        "supplier_id": env.ref("upgrade_prepare_demo.op_supplier_info_%s" % suffix).id,
                    },
                    "noupdate": True,
                }
            ]
        )
    _logger.info("Seeded %s replenishment rules for the orderpoint supplier tests", len(CASES))
