import logging

_logger = logging.getLogger(__name__)

# Siembra de los campos de busqueda extra de website_sale_search_improved
# (website_sale_search_improved.search_fields). En 20 el migration script
# (website_sale_search_improved/20.0.1.0.0/end-migration.py) tiene que sacar los que no existen y
# los que 20 ya busca solo. Lo verifica website_sale_search_improved/tests/expected_200.py.
#
# El parametro no tiene xmlid, asi que no hay ancla: se carga con uno propio para que el
# expected lo alcance. Una sola lista lleva todas las ramas:
#
#   x_upgrade_missing_field            -> sale (no existe)
#   product_tag_ids.x_upgrade_missing  -> sale (la ruta se corta a mitad de camino)
#   attribute_line_ids.value_ids.name  -> sale (20 lo busca solo)
#   description_ecommerce              -> queda (20 lo busca solo si se busca en descripciones)
#   website_meta_keywords              -> queda (existe y 20 no lo busca)
XMLID = "upgrade_prepare_demo.icp_website_sale_search_fields"
PARAM = "website_sale_search_improved.search_fields"
VALUE = str(
    [
        "x_upgrade_missing_field",
        "description_ecommerce",
        "attribute_line_ids.value_ids.name",
        "product_tag_ids.x_upgrade_missing",
        "website_meta_keywords",
    ]
)


def migrate(env):
    if "website_sale_search_improved" not in env["ir.module.module"].search([("state", "=", "installed")]).mapped(
        "name"
    ):
        return
    params = env["ir.config_parameter"].sudo()
    # The key is unique: a parameter saved from the settings, without xmlid, would block the load.
    params.search([("key", "=", PARAM)]).filtered(lambda param: not param.get_external_id()[param.id]).unlink()
    params._load_records([{"xml_id": XMLID, "values": {"key": PARAM, "value": VALUE}, "noupdate": True}])
    _logger.info("Seeded %s = %s", PARAM, VALUE)
