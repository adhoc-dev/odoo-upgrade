# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging
import os
import sys
import inspect
# no importamos base directamente porque si no trata de importar otras cosas y
# da error. Todo este lio para poder usar los obsolote y new obsolote en la
# mig y acá
base_path = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe())))
sys.path.append('%s/%s' % (base_path, 'base'))


from obsolte_modules import obsolte_modules
from new_obsolte_modules import new_obsolte_modules

# from obsolte_modules import obsolte_modules
# from new_obsolte_modules import new_obsolte_modules
_logger = logging.getLogger(__name__)


def run_scripts(env):
    _logger.info('Running post migration scripts')

    # re cargamos idioma español ar (antes que desinstalar para evitar
    # errores de cache)
    _logger.info('Cargando idioma español')
    wizard = env['base.language.install'].create(
        {'lang': 'es_AR', 'overwrite': True})
    wizard.with_context({'active_ids': [wizard.id]}).lang_install()

    errors = []

    # TODO ESTO LO HACEMOS DESDE SAAS UPGRADE

    #############################
    # CONTROL DE POSIBLES ERRORES
    #############################
    # lista de modulos que sabemos que se van a borrar y no tenemos que
    # alertarnos

    # tal vez esto no tiene mucho sentido y no deberiamos controlar nada de
    # esto, es decir, si estan en las otras listas, es porque estan depreciados
    ok_modules = [
        'web_support_client', 'web_support_client_issue', 'database_tools',
        'account_voucher', 'base_vat', 'disable_odoo_online',
        'admin_useful_groups', 'auth_admin_passkey',
        'auth_server_admin_passwd_passkey', 'account_invoice_tax_auto_update',
        'account_move_line_no_filter',
        'account_statement_disable_invoice_import', 'l10n_ar_account_check',
        'l10n_ar_account_voucher', 'l10n_ar_hide_receipts',
        'report_extended_voucher', 'account_financial_report_webkit_xls',
        'account_general_ledger_fix', 'account_journal_payment_subtype',
        'account_move_voucher', 'account_onchange_fix',
        'account_security_modifications', 'account_voucher_account_fix',
        'account_voucher_fix', 'account_voucher_payline',
        'cron_run_manually', 'partner_credit_limit', 'partner_search_by_ref',
        'partner_search_by_vat', 'partner_vat_unique', 'partner_views_fields',
        'partner_views_fields_base_vat', 'purchase_line_defaults',
        'purchase_product_men', 'purchase_usability_extension', 'report_xls',
        'sale_line_product_required', 'sale_usability_extension',
        'stock_display_destination_move', 'stock_display_sale_id',
        'web_search_with_and', 'web_widget_one2many_tags',
        'account_partner_account_summary', 'product_stock_location',
        'purchase_prices_update', 'account_multicompany_usability_withholding',
        'web_action_close_wizard_view_reload',
        'account_analytic_analysis_mods', 'crm_partner_history',
        'project_task_desc_html', 'project_task_order',
        'stock_picking_locations', 'account_voucher_multic_fix',
        'stock_multic_fix', 'account_analytic_project', 'contract_multic_fix',
        'partner_products_shortcut', 'account_contract_recurring_total',
        'sale_contract_default', 'purchase_product_menu', 'web_graph_sort',
        'website_server_mode', 'delivery_no_invoice_shipping', 'portal_fix',
        'portal_partner_fix', 'report_aeroo_portal_fix',
        'account_voucher_manual_reconcile', 'portal_welcome_email_template',
        'purchase_last_price_info', 'adhoc_base_account', 'adhoc_base_product',
        'adhoc_base_project', 'adhoc_base_purchase', 'adhoc_base_sale',
        'adhoc_base_setup', 'adhoc_base_stock', 'adhoc_base_website',
        'website_remove_product_legend', 'web_menu_hide',
        'website_sale_collapse_categories', 'web_snippet_extra',
        'product_computed_list_price_taxes_included',
        'project_issue_views_modifications', 'base_debug4all',
        'account_tax_settlement_withholding', 'account_voucher_constraint',
        'web_ir_actions_act_window_none', 'web_shortcuts',
        'account_voucher_double_validation', 'hr_timesheet_project',
        'product_uom_prices_currency', 'sale_stock_product_sale_uom',
        'stock_transfer_lot_filter', 'account_journal_sequence',
        'account_allow_code_change', 'website_sale_clear_line',
        'product_uom_prices']

    # esto es para generar mensajes de error, mas abajo se borran
    installed_obsoloete = env['ir.module.module'].search([
        ('name', 'in', obsolte_modules),
        ('name', 'not in', ok_modules)]).filtered(
        lambda x: x.state in ['to install', 'installed'])
    if installed_obsoloete:
        errors.append(
            'Se marcaron nuevos modulos a instalar pero están obsoletos:\n%s' %
            installed_obsoloete.mapped('name'))

    obsoloete = env['ir.module.module'].search([
        ('name', 'in', obsolte_modules),
        ('name', 'not in', ok_modules)]).filtered(
        lambda x: x.state == 'to upgrade')
    if obsoloete:
        errors.append(
            'Estos modulos quedaron para actualizar pero se borran porque '
            'no estarían mas\n%s' %
            obsoloete.mapped('name'))

    new_obsolete = env['ir.module.module'].search(
        [('name', 'in', new_obsolte_modules)]).filtered(
        lambda x: x.state == ['to install', 'installed', 'to upgrade'])
    if new_obsolete:
        errors.append(
            'Los new_obsolete devolvieron algo, cuidado!:\n%s' %
            new_obsolete.mapped('name'))

    ##########
    # LIMPIEZA
    ##########

    # desinstalamos y borramos modulos depreciados
    _logger.info('Uninstalling obsolte modules')
    # agregamos control de estados porque odoo no lo controla y los manda a
    # desinstalar por mas que hayan estado asi y entonces ya los considera
    # instalados, un desastre jeje
    # IMPORTANTE, al final desinstalamos los new_obsolote tmb
    env['ir.module.module'].search([
        ('name', 'in', obsolte_modules + new_obsolte_modules),
        ('state', 'in', ['installed', 'to upgrade'])]).button_uninstall()
    env['ir.module.module'].button_immediate_upgrade()

    _logger.info('Unlinking obsolte modules')
    env['ir.module.module'].search([
        ('name', 'in', obsolte_modules),
        ('state', 'in', ['uninstalled', 'uninstallable'])]).unlink()

    # nuevo para limpiar mas modulos
    _logger.info('Unlinking new obsolte modules')
    env['ir.module.module'].search([
        ('name', 'in', new_obsolte_modules),
        ('state', 'in', ['uninstalled', 'uninstallable'])]).unlink()

    # limpiamos parametros viejos de aeroo
    env['ir.config_parameter'].search([('key', 'ilike', 'aeroo')]).unlink()

    # volvemos a poner base en version que corresponde
    _logger.info('Updating base module version')
    env.cr.execute(
        "UPDATE ir_module_module SET latest_version = '9.0.1.3' "
        "WHERE name = 'base'")

    # fix de auto search
    _logger.info('Fix de auto search que no funciona bien')
    env.cr.execute("""
        UPDATE ir_act_window SET auto_search = true WHERE id in
        (SELECT res_id from ir_model_data WHERE name in
            ('product_template_action', 'product_normal_action_sell',
                'action_partner_form')
            and module in ('base', 'product'))""")

    return errors
