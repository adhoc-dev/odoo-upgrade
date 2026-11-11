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
    # base/0.0.0/end-220-fix_mail_templates.py: las plantillas que cambio el
    # cliente se prueban con los ultimos registros del modelo. Siembra en
    # tests/pre_odu/mail/190_200/010-customer_mail_templates.py.
    "mail.template": {
        # No renderiza y no viene de un modulo, asi que no se puede resetear:
        # el script la archiva. Si sigue activa, no la probo o no la detecto.
        ref("upgrade_prepare_demo.mail_template_customer_broken"): {
            "active": False,
        },
        # Preservacion: una plantilla del cliente que renderiza queda activa.
        # Si se archivo, el script marca como rota una que anda.
        ref("upgrade_prepare_demo.mail_template_customer_healthy"): {
            "active": True,
        },
        # Falla solo con la etiqueta archivada: el error es del dato y no se
        # toca. Si se archivo, el script no probo con varios registros.
        ref("upgrade_prepare_demo.mail_template_customer_partial"): {
            "active": True,
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

# Los scripts de base/0.0.0 corren en todos los saltos: este EXPECTED verifica
# los de SCRIPTS, y el resto queda en NO_CHECK con su motivo.
SCRIPTS = ["end-110-reload_translations.py", "end-220-clean_broken_filters.py"]

IN_MEMORY = "Parchea un metodo en memoria mientras corre el -u: no deja nada en la base para verificar."
ONLY_WARNS = "Solo avisa en el log: no cambia datos."
GONE = "Borra un registro, y el check no puede declarar una ausencia: lo cubre su test en modules/base/tests/."
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
    "end-230-drop_variant_preselect_parameter.py": GONE,
    "end-900-uninstall_not_available_modules.py": PENDING,
    "post-01-modules-auto-discovery.py": PENDING,
    "pre-0-disable-check-company.py": IN_MEMORY,
    "pre-0-disable-check-views.py": IN_MEMORY,
    "pre-0-model-checks.py": IN_MEMORY,
}
