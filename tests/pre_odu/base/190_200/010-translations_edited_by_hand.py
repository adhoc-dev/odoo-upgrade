import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-110-reload_translations.py, que en los saltos a 20
# recarga las traducciones de los idiomas activos pisando las de la base. Los
# verifica base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: los menus de abajo ya estan en la base canonica con
# su xmlid, pero con la traduccion del .po. Lo que el script cambia es una
# traduccion editada a mano, y esa no la trae ninguna data de prueba. Se edita
# un menu de core, uno nuestro y uno de OCA, porque cada uno trae su .po.
#
# El producto es la rama de preservacion: un registro del cliente, sin .po, con
# su traduccion. El script no tiene de donde recargarla y tiene que quedar igual.
#
# Solo se toca es_AR. Si no esta activo se activa: sin un idioma activo el
# script no recarga nada y el check no tendria que verificar.

LANG = "es_AR"
EDITED = "Editado a mano"
EDITED_MENUS = (
    "sale.sale_menu_root",
    "account_ux.menu_customer_ledger",
    "sale_order_type.sot_sale_order_type_menu",
)
PRODUCT_XMLID = "upgrade_prepare_demo.product_translated_by_hand"


def migrate(env):
    if not env["res.lang"].search_count([("code", "=", LANG)]):
        lang = env["res.lang"]._activate_lang(LANG)
        env["base.language.install"].create({"lang_ids": [(6, 0, lang.ids)]}).lang_install()

    for xmlid in EDITED_MENUS:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu:
            # Sin el menu no hay caso: lo dice el check como ref ausente
            _logger.info("%s is not in this database - not seeding it", xmlid)
            continue
        menu.update_field_translations("name", {LANG: EDITED})

    env["product.template"]._load_records(
        [{"xml_id": PRODUCT_XMLID, "values": {"name": "Product translated by hand"}, "noupdate": True}]
    )
    env.ref(PRODUCT_XMLID).update_field_translations("name", {LANG: "Producto traducido a mano"})
