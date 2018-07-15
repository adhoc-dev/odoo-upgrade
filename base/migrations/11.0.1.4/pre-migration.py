from openupgradelib import openupgrade, openupgrade_merge_records
from odoo.addons.base import dynamic_data

# traer actualizado de
# https://github.com/OCA/OpenUpgrade/blob/11.0/odoo/addons/openupgrade_records/lib/apriori.py
renamed_modules = {
    # OCA/credit-control
    'partner_financial_risk': 'account_financial_risk',
    'partner_payment_return_risk': 'account_payment_return_financial_risk',
    'partner_sale_risk': 'sale_financial_risk',
    # OCA/stock-logistics-reporting
    'stock_valued_picking_report': 'stock_picking_report_valued',
    # OCA/vertical-association
    'membership_prorrate': 'membership_prorate',
    'membership_prorrate_variable_period': (
        'membership_prorate_variable_period'
    ),
    ## de adhoc
    # modulos usability
    'account_usability': 'account_ux',
    'sale_usability': 'sale_ux',
    'project_usability': 'project_ux',
    'project_issue_order': 'helpdesk_ux',
    'base_usability': 'base_ux',
    'portal_usability': 'portal_ux',
    'website_sale_usability': 'website_sale_ux',
    'product_usability': 'product_ux',
    'stock_usability': 'stock_ux',
    'mrp_usability': 'mrp_ux',
    'sale_usability_stock': 'sale_stock_ux',
    'crm_voip_usability': 'crm_voip_ux',
    'purchase_usability': 'purchase_ux',
    'mrp_repair_usability': 'mrp_repair_ux',
    'sale_contract_usability': 'sale_subscription_ux',
    'website_quote_usability': 'sale_timesheet_ux',
    'sale_usability_delivery': 'sale_delivery_ux',
    'stock_usability_batch_picking': 'stock_batch_picking_ux',
    'account_multicompany_usability': 'account_multicompany_ux',
    # otros modulos
    'website_project_issue_solution': 'website_helpdesk_solution',
    'project_issue_solutions': 'helpdesk_solutions',
    'product_computed_list_price': 'product_planned_price',
    'sale_order_type_sequence': 'sale_oder_type_ux',
    'purchase_contract': 'purchase_subscription',
}

# TODO borrar
# 'project_usability_issue'
# 'stock_usability_quant_manual_assign'
merged_modules = {
    # OCA/account-financial-reporting
    # Done here for avoiding problems if updating from a previous version
    # where account_financial_report exists as other kind of module
    'account_financial_report_qweb': 'account_financial_report',
    # OCA/bank-payment
    'portal_payment_mode': 'account_payment_mode',
    # OCA/stock-logistics-workflow
    'stock_picking_transfer_lot_autoassign': 'stock_pack_operation_auto_fill',
    ## de adhoc
    'stock_picking_control': 'stock_ux',
    'sale_contract_lines_sequence': 'sale_subscription_ux',
    'product_replenishment_cost_rule': 'product_replenishment_cost',
    'product_replenishment_cost_currency': 'product_replenishment_cost',
    'product_price_currency': 'product_planned_price',
    'product_sale_price_by_margin': 'product_planned_price',
    'sale_order_type_user_default': 'sale_oder_type_ux',
    'account_journal_active': 'account',
    'project_kanban_open_project': 'project_ux',
    'adhoc_modules': 'saas_client',
    'adhoc_modules_server': 'saas_provider',
    'product_website_categ_search': 'website_sale_ux',
    'account_reconciliation_menu': 'account_ux',
    'l10n_ar_afipws_fe_cancel': 'l10n_ar_afipws_fe',
    # esto es por el campo afip_code que antes lo creaba l10n_ar_states
    'l10n_ar_states': 'l10n_ar_account',
    'sale_usability_return_invoicing': 'sale_ux',
    'purchase_usability_return_invoicing': 'purchase_ux',
}


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr

    if dynamic_data.renamed_modules:
        renamed_modules = dynamic_data.renamed_modules
    if dynamic_data.merged_modules:
        merged_modules = dynamic_data.merged_modules

    openupgrade.update_module_names(cr, renamed_modules.items())
    openupgrade.update_module_names(
        cr, merged_modules.items(), merge_modules=True)

    fix_aeroo_reports(cr)


def fix_aeroo_reports(cr):
    openupgrade.logged_query(cr, """
        UPDATE ir_act_report_xml SET parser_state = 'default',
            parser_loc = false
    """)
