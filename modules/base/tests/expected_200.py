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
# Y de base/0.0.0/end-220-clean_broken_filters.py: los favoritos que usan un
# campo que no existe en la base nueva pierden esa condicion, el group by y el
# orden sobre ese campo; si no les queda ninguna condicion, se archivan.
#
#   campo roto en un OR, con otra condicion  -> se limpia y sigue activo
#   campo roto en un camino, group by texto  -> se limpia y sigue activo
#   solo el campo roto                       -> se archiva
#   solo el campo roto, con "not =like"      -> se archiva
#   campo roto y una condicion "not =ilike"  -> se limpia y sigue activo
#   todos los campos existen                 -> no se toca (preservacion)
#
# Los siembra tests/pre_odu/base/190_200/020-filters_with_missing_fields.py,
# con un campo que no existe en ninguna version.
#
# Y de base/0.0.0/end-190-restore_website_custom_views.py: despues de que
# end-180 deprecia las vistas del sitio que el cliente tenia modificadas, cada
# una vuelve al estado que tenia antes de actualizar.
#
#   copia del sitio prendida      -> vuelve prendida, con su key
#   copia del sitio apagada       -> recupera su key y sigue archivada
#   copia con key en IGNORE_KEYS  -> no se toca (preservacion)
#   lista de deseos apagada       -> el website pierde las dos clases de la opcion
#
# Las siembra tests/pre_odu/base/190_200/030-website_custom_views.py, porque
# una copia de website solo nace editando el sitio desde el editor.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "ir.filters": {
        # La condicion sobre el campo roto queda como siempre falsa: en un OR,
        # el favorito sigue buscando por nombre. El group by sobre el campo se
        # va. Si el dominio sigue con el campo, el script no lo detecto.
        ref("upgrade_prepare_demo.filter_missing_field_in_or"): {
            "domain": "['|', ('name', 'ilike', 'Upgrade'), (0, '=', 1)]",
            "context": "{'group_by': []}",
            "sort": '["name"]',
            "active": True,
        },
        # Sin ninguna condicion real, mostraria todos los contactos: se
        # archiva. Si sigue activo, el script no lo archivo.
        ref("upgrade_prepare_demo.filter_only_missing_field"): {
            "active": False,
        },
        # El campo roto esta en el segundo tramo del camino, y el group by viene
        # como texto: si el dominio sigue con el camino, o el group by quedo
        # partido en letras, el script no lo limpio bien.
        ref("upgrade_prepare_demo.filter_missing_field_in_path"): {
            "domain": "['|', ('name', 'ilike', 'Upgrade'), (0, '=', 1)]",
            "context": "{'group_by': [], 'pivot_measures': []}",
            "sort": "[]",
            "active": True,
        },
        # "not =like" es un operador de condicion: si sigue activo, el script
        # no vio el campo roto.
        ref("upgrade_prepare_demo.filter_missing_field_not_like"): {
            "active": False,
        },
        # En un AND, la condicion sobre el campo roto queda como siempre
        # verdadera, y la de "not =ilike" sigue. Si se archivo, el script no la
        # conto como condicion.
        ref("upgrade_prepare_demo.filter_missing_field_and_not_ilike"): {
            "domain": "['&', (1, '=', 1), ('name', 'not =ilike', 'foo')]",
            "active": True,
        },
        # Preservacion: todos sus campos existen, y "-id" es el formato viejo de
        # orden descendente, no un campo; "__count" tampoco. Si cambia, el script
        # toco un favorito que no estaba roto.
        ref("upgrade_prepare_demo.filter_valid_fields"): {
            "domain": "[('name', 'ilike', 'Upgrade'), ('type', 'in', ['contact', 'invoice', 'delivery'])]",
            "context": "{'group_by': ['country_id']}",
            "sort": '["name desc", "-id", "__count desc"]',
            "active": True,
        },
    },
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
    "ir.ui.view": {
        # Estaba prendida antes de actualizar: end-180 la deprecia y end-190 la
        # tiene que dejar como estaba. Si llega con la key terminada en
        # "_depreciada" o archivada, end-190 no la puso de vuelta.
        ref("upgrade_prepare_demo.website_view_on"): {
            "key": "upgrade_prepare_demo.website_view_on",
            "active": True,
        },
        # Estaba apagada: recupera su key y sigue archivada. Si queda prendida,
        # end-190 leyo mal el estado viejo; si queda con la key depreciada, deja
        # de pisar a la generica y la version nueva prende la opcion sola.
        ref("upgrade_prepare_demo.website_view_off"): {
            "key": "upgrade_prepare_demo.website_view_off",
            "active": False,
        },
        # Preservacion: su key esta en IGNORE_KEYS de end-180, asi que nadie la
        # deprecia. Si cambia, end-180 dejo de respetar su lista.
        ref("upgrade_prepare_demo.website_view_ignored"): {
            "key": "website_sale.products_oe_structure_website_sale_products_1",
            "active": True,
        },
        # La copia de la lista de deseos: estaba apagada, asi que recupera su key y
        # sigue archivada, igual que website_view_off. Es la mitad "vista" del caso;
        # la otra mitad la mira el website de abajo.
        ref("upgrade_prepare_demo.website_view_wishlist"): {
            "key": "website_sale_wishlist.add_to_wishlist",
            "active": False,
        },
    },
    "website": {
        # La lista de deseos estaba apagada en la base vieja: end-190 le saca las dos
        # clases de la opcion y deja el resto como estaba. Si quedan, la opcion se
        # prende sola en 20, donde ya no depende de la vista; si el campo queda
        # vacio, el script saco de mas.
        ref("website.default_website"): {
            "shop_opt_products_design_classes": "o_wsale_products_opt_cc1",
        },
    },
}

# Los scripts de base/0.0.0 corren en todos los saltos: este EXPECTED verifica
# los de SCRIPTS, y el resto queda en NO_CHECK con su motivo.
SCRIPTS = [
    "end-110-reload_translations.py",
    "end-190-restore_website_custom_views.py",
    "end-220-clean_broken_filters.py",
]

IN_MEMORY = "Parchea un metodo en memoria mientras corre el -u: no deja nada en la base para verificar."
ONLY_WARNS = "Solo avisa en el log: no cambia datos."
PENDING = "Pendiente: es de antes de la regla del ADR 0037 de actua-20, falta escribirle el check."

NO_CHECK = {
    "end-020-restore_active_crons.py": PENDING,
    "end-030-restore_manual_related_fields.py": PENDING,
    "end-040-drop_generated_manual_field_xmlids.py": PENDING,
    "end-050-repoint_invoice_lines_analysis_action.py": PENDING,
    "end-060-check_credit_card_journals.py": ONLY_WARNS,
    "end-070-restore_dashboard_groups.py": PENDING,
    "end-080-restore_website_snippet_views.py": PENDING,
    "end-090-drop_upgrade_test_ribbon.py": PENDING,
    "end-100-drop_upgrade_view_copies.py": PENDING,
    "end-120-support_users_all_companies.py": PENDING,
    "end-130-check_orphan_activities.py": ONLY_WARNS,
    "end-140-fix_partner_timezones.py": PENDING,
    "end-150-unify_reconcile_model_labels.py": PENDING,
    "end-160-deactivate_problem_views.py": PENDING,
    "end-170-drop_dashboard_custom_views.py": PENDING,
    "end-180-deprecate_website_custom_views.py": PENDING,
    "end-200-replace_success_upgrade_message.py": PENDING,
    "end-210-check_personalizations.py": PENDING,
    "end-900-uninstall_not_available_modules.py": PENDING,
    "post-01-modules-auto-discovery.py": PENDING,
    "pre-0-disable-check-company.py": IN_MEMORY,
    "pre-0-disable-check-views.py": IN_MEMORY,
    "pre-0-model-checks.py": IN_MEMORY,
}
