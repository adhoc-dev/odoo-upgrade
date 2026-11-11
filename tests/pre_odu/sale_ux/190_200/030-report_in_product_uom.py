import logging

_logger = logging.getLogger(__name__)

# Siembra del parametro que sale_product_uom_price 19 usaba para mostrar los presupuestos en la
# unidad del producto (sale_product_uom_price.report_in_product_uom). En 20 el modulo se fusiona
# en sale_ux, que lee sale_ux.report_in_product_uom, y el migration script
# (sale_ux/20.0.0.0/pre-migration.py) tiene que renombrar la clave. Lo verifican los tests
# declarativos (sale_ux/tests/expected_200.py).
#
# El parametro no tiene xmlid, asi que se le da uno bajo upgrade_prepare_demo para que el
# expected lo encuentre despues del renombre. Se reusa el parametro si ya estaba (la clave es
# unica) y _update_xmlids no duplica el xmlid: re-correr no duplica nada.
PARAM = "sale_product_uom_price.report_in_product_uom"
XMLID = "upgrade_prepare_demo.param_report_in_product_uom"


def migrate(env):
    if "sale_ux" not in env["ir.module.module"].search([("state", "=", "installed")]).mapped("name"):
        return
    params = env["ir.config_parameter"].sudo()
    param = params.search([("key", "=", PARAM)])
    if param:
        param.value = "True"
    else:
        param = params.create({"key": PARAM, "value": "True"})
    env["ir.model.data"]._update_xmlids([{"xml_id": XMLID, "record": param, "noupdate": True}])
    _logger.info("Seeded %s = True", PARAM)
