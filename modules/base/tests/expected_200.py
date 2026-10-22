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

# Los scripts de base/0.0.0 corren en todos los saltos: este EXPECTED verifica
# los de SCRIPTS, y el resto queda en NO_CHECK con su motivo.
SCRIPTS = ["end-110-reload_translations.py"]

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
