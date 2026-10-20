# Test declarativo de base/0.0.0/end-110-reload_translations.py en el salto a 20.
#
# La transformacion: al final del -u el script recarga las traducciones de los
# idiomas activos desde los .po de la version nueva, pisando las de la base.
#
#   termino que trae un .po, editado a mano  -> vuelve al valor del .po
#   registro del cliente, sin .po            -> no se toca (preservacion)
#
# La siembra edita en es_AR un menu de core, uno nuestro y uno de OCA
# (tests/pre_odu/base/190_200/010-translations_edited_by_hand.py): cada uno trae
# su propio .po, y el script los recarga todos.
#
# Los valores esperados son los de los .po de 20. Si un .po cambia la
# traduccion de uno de estos menus, el check falla aunque el script ande: se
# actualiza el valor declarado.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "ir.ui.menu": {
        # Core: la siembra dejo "Editado a mano" en es_AR. Si sigue asi, el
        # script no recargo las traducciones, o no las piso.
        ref("sale.sale_menu_root"): {
            "name@es_AR": "Ventas",
        },
        # Un modulo nuestro, con su .po: el script tiene que recargar los .po
        # de todos los modulos instalados, no solo los de Odoo.
        ref("account_ux.menu_customer_ledger"): {
            "name@es_AR": "Mayor de Clientes",
        },
        # Un modulo de OCA: lo mismo, con un .po que no es ni de Odoo ni nuestro.
        ref("sale_order_type.sot_sale_order_type_menu"): {
            "name@es_AR": "Tipos de pedido de venta",
        },
    },
    "product.template": {
        # Preservacion: un registro del cliente con su traduccion, sin .po. Si
        # cambia, el script piso algo que no tenia de donde recargar.
        ref("upgrade_prepare_demo.product_translated_by_hand"): {
            "name@es_AR": "Producto traducido a mano",
        },
    },
}
