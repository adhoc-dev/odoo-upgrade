import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-190-restore_website_custom_views.py, que en los saltos a
# 20 le devuelve a cada vista del sitio el estado que tenia antes de actualizar.
# Los verifica base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: una copia de website nace cuando alguien edita el sitio
# desde el editor, y ninguna data de prueba trae una. Sin copias, end-180 no
# deprecia nada y end-190 no tiene nada que poner de vuelta.
#
# La de preservacion lleva una key de IGNORE_KEYS de end-180, y a proposito una
# que el core NO define como template (las "oe_structure" las crea el editor):
# con la key de un template vivo, la copia primaria lo taparia en las busquedas
# por key y el caso pasaria por el motivo equivocado.
#
# La de la lista de deseos sirve a la otra mitad del script: en 20 el addon
# website_sale_wishlist ya no existe y la opcion son dos clases del website, asi
# que el estado viejo solo se puede leer de esta copia apagada.

ARCH = '<div class="upgrade_prepare_demo_website_view">Upgrade</div>'
WISHLIST_KEY = "website_sale_wishlist.add_to_wishlist"
# Las dos de la lista de deseos tienen que salir; la tercera se queda, y es la que
# distingue "saco las que corresponden" de "vacio el campo".
DESIGN_CLASSES = "o_wsale_products_opt_has_wishlist o_wsale_products_opt_wishlist_fixed o_wsale_products_opt_cc1"

VIEWS = [
    # Prendida antes de actualizar: end-180 la deprecia y end-190 la tiene que
    # volver a prender con su key original.
    ("upgrade_prepare_demo.website_view_on", "upgrade_prepare_demo.website_view_on", True),
    # Apagada antes de actualizar: end-190 le devuelve la key y la deja archivada,
    # para que deje de pisar a la generica y la version nueva no prenda la opcion.
    ("upgrade_prepare_demo.website_view_off", "upgrade_prepare_demo.website_view_off", False),
    # Preservacion: su key esta en IGNORE_KEYS, asi que end-180 no la deprecia y
    # end-190 no la tiene que tocar.
    (
        "upgrade_prepare_demo.website_view_ignored",
        "website_sale.products_oe_structure_website_sale_products_1",
        True,
    ),
    # Lista de deseos apagada para este sitio: end-190 tiene que sacarle las dos
    # clases al website, ademas de devolverle la key a la copia.
    ("upgrade_prepare_demo.website_view_wishlist", WISHLIST_KEY, False),
]


def migrate(env):
    website = env.ref("website.default_website", raise_if_not_found=False)
    if not website:
        _logger.warning("Sin website instalado: no se sembraron las copias de vistas del sitio")
        return

    for xmlid, key, active in VIEWS:
        env["ir.ui.view"]._load_records(
            [
                {
                    "xml_id": xmlid,
                    "values": {
                        "name": xmlid.split(".")[1],
                        "type": "qweb",
                        "key": key,
                        "arch": ARCH,
                        "website_id": website.id,
                        "active": active,
                    },
                    "noupdate": True,
                }
            ]
        )

    # Valor fijo y no el default de la version, para que el esperado no dependa de
    # lo que traiga cada una. Idempotente: vuelve a escribir lo mismo.
    website.write({"shop_opt_products_design_classes": DESIGN_CLASSES})
    _logger.info("Sembradas %s copias de vistas del sitio y las clases del shop", len(VIEWS))
