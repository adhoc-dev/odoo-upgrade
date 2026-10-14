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
    # base/0.0.0/end-220-journal_book_groups_to_ledgers.py: pasa los grupos del
    # libro diario a Ledgers (siembra en
    # tests/pre_odu/account_journal_book_report/190_200/010-book_group_cases.py).
    # Fuera de este check: que un diario con grupo reciba su Ledger nuevo, con o
    # sin sufijo. El Ledger lo crea el script, sin xmlid, y no hay ref() que lo
    # declare.
    "account.journal": {
        # Preservacion: el diario no tenia grupo del libro diario. Si queda con
        # un Ledger, el script se lo asigno sin grupo, o el pase a Odoo le dio
        # el Ledger sembrado que lo excluia.
        ref("upgrade_prepare_demo.journal_book_group_none"): {
            "journal_group_id": None,
        },
    },
    "account.journal.group": {
        # Choque de nombre: un grupo se llama como este Ledger, que ya existia.
        # El script crea otro Ledger con sufijo y a este no lo toca. Si cambia
        # el nombre, el script reuso o renombro el Ledger del cliente.
        ref("upgrade_prepare_demo.ledger_book_group_clash"): {
            "name": "Upgrade case ledger clash",
        },
    },
}
