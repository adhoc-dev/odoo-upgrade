import logging

_logger = logging.getLogger(__name__)

# Ordenes de venta confirmadas con y sin facturacion forzada (sale_ux.force_invoiced_status).
# En 20 Odoo trae un cierre propio (invoicing_closed) que NO alcanza: solo marca la orden, las
# lineas siguen "A facturar". sale_ux conserva su campo y su logica, y el dato tiene que
# sobrevivir al pase: si se pierde, las ordenes forzadas vuelven a "A facturar" y Odoo propone
# facturarlas. Los verifican los tests declarativos (sale_ux/tests/expected_200.py).
#
# Cada caso es una orden con una linea, las dos con xmlid estable porque el expected
# verifica tambien la linea (el estado de facturacion y el monto a facturar viven ahi).
# _load_records (nativo de BaseModel) es idempotente: re-correr no duplica registros.
CASES = [
    # (nombre, force_invoiced_status)
    ("so_force_invoiced", "invoiced"),
    ("so_force_nothing", "no"),
    # Preservacion: orden sin forzar, tiene que seguir "A facturar".
    ("so_not_forced", False),
]
MODULE = "upgrade_prepare_demo"


def migrate(env):
    if "force_invoiced_status" not in env["sale.order"]._fields:
        return
    partner = env["res.partner"].search([("is_company", "=", True)], limit=1)
    product = env["product.product"].search(
        [("type", "=", "consu"), ("sale_ok", "=", True), ("invoice_policy", "=", "order")], limit=1
    )
    if not (partner and product):
        _logger.warning("No partner or product to seed the sale orders: skipped")
        return
    for name, forced in CASES:
        values = {"partner_id": partner.id, "state": "sale"}
        if forced:
            values["force_invoiced_status"] = forced
        env["sale.order"]._load_records([{"xml_id": "%s.%s" % (MODULE, name), "values": values, "noupdate": True}])
        order = env.ref("%s.%s" % (MODULE, name))
        line_values = {"order_id": order.id, "product_id": product.id, "product_uom_qty": 1.0, "price_unit": 100.0}
        env["sale.order.line"]._load_records(
            [{"xml_id": "%s.%s_line" % (MODULE, name), "values": line_values, "noupdate": True}]
        )
