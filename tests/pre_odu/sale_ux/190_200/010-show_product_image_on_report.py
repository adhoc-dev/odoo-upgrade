import logging

_logger = logging.getLogger(__name__)

# Siembra del parametro que sale_ux 19 usaba para mostrar la imagen del producto en el
# presupuesto (sale_ux.show_product_image_on_report, global). En 20 la imagen se muestra con el
# ajuste nativo de la compania, y el migration script
# (sale_ux/20.0.0.0/post-migration.py) tiene que pasarlo. Lo verifican los tests declarativos
# (sale_ux/tests/expected_200.py).
#
# El parametro no tiene xmlid, asi que no hay ancla que sirva: sin esta siembra la base
# canonica no lo tiene prendido y el check pasaria en verde sin haber probado nada.
# Se escribe con el ORM generico (search/write/create) y no con set_param, porque esa API
# no existe en todas las versiones.
PARAM = "sale_ux.show_product_image_on_report"


def migrate(env):
    if "sale_ux" not in env["ir.module.module"].search([("state", "=", "installed")]).mapped("name"):
        return
    params = env["ir.config_parameter"].sudo()
    param = params.search([("key", "=", PARAM)])
    if param:
        param.value = "True"
    else:
        params.create({"key": PARAM, "value": "True"})
    _logger.info("Seeded %s = True", PARAM)
