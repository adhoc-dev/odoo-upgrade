renamed_modules = {
  # v12
  'account_payment_return_import_sepa_pain': 'account_payment_return_import_iso20022',
  'product_uom_unece': 'uom_unece',
  'crm_deduplicate_acl': 'partner_deduplicate_acl',
  'crm_deduplicate_filter': 'partner_deduplicate_filter',
  'hr_employee_seniority': 'hr_employee_service_contract',
  'stock_pack_operation_auto_fill': 'stock_move_line_auto_fill',
  'website_quote_public': 'sale_quotation_ux',
  'helpdesk_project_ux' : 'helpdesk_timesheet_ux',
  # v13
  'saas_client_mass_editing': 'saas_client_mass_operation_abstract',
  'logos_product_attributes': 'logos_personalization',
  'legal': 'personalizations_royr',
}


merged_modules = {
  # v12
  'website_sale_default_country': 'website_sale',
  'base_partner_merge': 'base',
  'auth_brute_force': 'base',
  'stock_putaway_product': 'stock',
  'product_supplierinfo_discount' : 'product_discount',
  'server_mode_mail': 'server_mode',
  'server_mode_fetchmail': 'server_mode',
  'website_quote_ux': 'sale_ux',
  'sale_subscription_invoice_address': 'sale_subscription_ux',
  'account_reports_ux': 'account_accountant_ux',
  'account_fix': 'account_ux',
  'account_asset_management': 'account_asset',
  'portal_sale_distributor_wesbite_quote': 'portal_sale_distributor',
  # v13
  'transindar_personalization': 'personalizations_ingenieriaboggio',
  'logos_personalization': 'personalizations_edicioneslogos',
  'l10n_ar_chart': 'l10n_ar',
  'account_clean_cancelled_invoice_number': 'account_ux',
  # 'account_type_menu': 'account_menu', # a este lo depreciamos
  'account_document': 'l10n_latam_invoice_document',
  'l10n_ar_account': 'l10n_ar_ux', # lo hacemos a l10n_ar_ux para renombrar menos xmlids y tmb que se auto instale
  'l10n_ar_afipws': 'l10n_ar_edi_ux', # lo hacemos a l10n_ar_edi pa que se auto instale
  'l10n_ar_afipws_fe': 'l10n_ar_edi',
  'l10n_ar_partner': 'l10n_latam_base',
}


xmlid_renames = [
  # creo que fuimos y vinimos con v11/v12 con esto y nos da error en algunos casos, de ultima se vuelve a activar o lo hacemos con post script
  # ('account_financial_amount.account_use_financial_amounts', 'account_debt_management.account_use_financial_amounts'),
  # ('account_debt_management.account_use_financial_amounts', 'account_financial_amount.account_use_financial_amounts'),
  ('purchase_ux.field_purchase_order_force_delivered_status', 'purchase_stock_ux.field_purchase_order_force_delivered_status'),
  ('purchase_ux.field_purchase_order_delivery_status', 'purchase_stock_ux.field_purchase_order_delivery_status'),
  ('purchase_ux.field_purchase_order_line_delivery_status', 'purchase_stock_ux.field_purchase_order_line_delivery_status'),
  ('purchase_ux.field_purchase_order_with_returns', 'purchase_stock_ux.field_purchase_order_with_returns'),
  ('purchase_ux.field_purchase_order_line_qty_returned', 'purchase_stock_ux.field_purchase_order_line_qty_returned'),
  ('saas_client.login', 'saas_client_adhoc.login'),
  ('saas_client.group_hidden_resources', 'saas_client_adhoc.group_hidden_resources'),
  ('saas_client.field_saas_client_changelog__description', 'saas_client_adhoc.field_saas_client_changelog__description'),
  ('saas_client.field_saas_client_changelog__date', 'saas_client_adhoc.field_saas_client_changelog__date'),
  ('saas_client.field_saas_client_changelog__name', 'saas_client_adhoc.field_saas_client_changelog__name'),
  ('saas_client.model_saas_client_changelog', 'saas_client_adhoc.model_saas_client_changelog'),
  ('saas_client.field_res_users__portal_access', 'saas_client_adhoc.field_res_users__portal_access'),
  ('saas_client.field_res_users__authorized_for_issues', 'saas_client_adhoc.field_res_users__authorized_for_issues'),
  # para los campos no hace falta y nos queremos evitar posible error
  # ('saas_client.field_res_users__saas_provider_uuid', 'saas_client_adhoc.field_res_users__saas_provider_uuid'),
  ('saas_client.group_hidden_resources', 'saas_client_adhoc.group_hidden_resources'),
  ('saas_client.contract_adhoc_modules', 'saas_client_adhoc.contract_adhoc_modules'),
  ('saas_client.disable_inactive_users', 'saas_client_adhoc.disable_inactive_users'),
]
