import logging

_logger = logging.getLogger(__name__)

# Casos de modules/helpdesk_stock_ux/20.0.1.0.0/post-migration.py, que despues del pase a 20
# vuelve a escribir el producto y el lote de los tickets desde el respaldo del pre_odoo. Los
# verifica modules/helpdesk_stock_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: ningun ticket de la data de prueba trae producto ni lote. Las
# vistas estandar de 18 y 19 no muestran los dos campos: en las bases de clientes se cargan
# por helpdesk_stock_ux, y en la base canonica no los carga nadie.
#
# El producto y el lote tambien se siembran, con xmlid propio: el expected los nombra del
# lado del valor, y lo que verifica es que el ticket vuelva a apuntar a esos mismos
# registros despues del pase.

PRODUCT_XMLID = "upgrade_prepare_demo.hst_tracked_product"
LOT_XMLID = "upgrade_prepare_demo.hst_tracked_lot"
TICKETS = (
    ("hst_ticket_product_and_lot", True, True),
    ("hst_ticket_only_product", True, False),
    # Rama de preservacion: sin producto ni lote, no entra en el respaldo.
    ("hst_ticket_without_product", False, False),
)


def migrate(env):
    if "helpdesk.ticket" not in env or "product_id" not in env["helpdesk.ticket"]._fields:
        # Sin helpdesk_stock no hay caso: lo dice el check como ref ausente.
        _logger.info("helpdesk.ticket has no product_id in this database - not seeding it")
        return

    env["product.product"]._load_records(
        [
            {
                "xml_id": PRODUCT_XMLID,
                "values": {
                    "name": "Helpdesk stock ux product",
                    "type": "consu",
                    "is_storable": True,
                    "tracking": "lot",
                    "sale_ok": True,
                },
                "noupdate": True,
            }
        ]
    )
    product = env.ref(PRODUCT_XMLID)
    env["stock.lot"]._load_records(
        [
            {
                "xml_id": LOT_XMLID,
                "values": {"name": "HST-0001", "product_id": product.id},
                "noupdate": True,
            }
        ]
    )
    lot = env.ref(LOT_XMLID)

    records = []
    for name, with_product, with_lot in TICKETS:
        values = {"name": name.replace("_", " ").capitalize()}
        if with_product:
            values["product_id"] = product.id
        if with_lot:
            values["lot_id"] = lot.id
        records.append({"xml_id": "upgrade_prepare_demo.%s" % name, "values": values, "noupdate": True})
    # product_id solo lo ve un usuario de Inventario.
    env["helpdesk.ticket"].sudo()._load_records(records)
