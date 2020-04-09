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
  'l10n_ar_chart': 'l10n_ar',
  'account_clean_cancelled_invoice_number': 'account_ux',
  'account_type_menu': 'account_menu',
  'account_document': 'l10n_latam_invoice_document',
  'l10n_ar_account': 'l10n_ar_ux', # lo hacemos a l10n_ar_ux para renombrar menos xmlids y tmb que se auto instale
  'l10n_ar_afipws': 'l10n_ar_edi_ux', # lo hacemos a l10n_ar_edi pa que se auto instale
  'l10n_ar_afipws_fe': 'l10n_ar_edi',
  'l10n_ar_partner': 'l10n_latam_base',
}


to_remove = [
  # de v12
  'product_variant_o2o', 'account_move_helper', 'snippet_google_map', 'saas_client_subscription', 'password_security', 'web_widget_datepicker_options',
  'base_partner_merge', 'portal_ux', 'web_sheet_full_width', 'stock_analysis_aeroo_report', 'account_reports_cash_flow', 'stock_inventory_require_lot', 'sale_restrict_partners',
  'account_financial_report_date_range',
  'project_timeline_task_dependency',
  # de v13
  'web_widget_many2many_tags_multi_selection',
  'google_cloud_print',
  'l10n_ar_aeroo_einvoice',
  'l10n_ar_aeroo_invoice',
  'base_validator',
  'partner_identification',
  'base_vat_sanitized',
  'saas_client_sale_timesheet',
  'website_logo',
  'web_editor_background_color', # nativo en odoo
  # modulos que odoo auto-instalaba pero que nosotros no usamos y ahora NO auto instalamos
  'account_facturx',
  'account_bank_statement_import_ofx',
  'account_bank_statement_import_camt',
  'account_invoice_extract',
  'account_ponto',
  'account_yodlee',
  'account_plaid',
  'account_taxcloud',
  # probamos depreciar:
  'web_export_view', # ALGO SIMILAR ES NATIVO EN ODOO
  'partner_external_map', # ALGO SIMILAR ES NATIVO EN ODOO
  'account_debt_management',
  'survey_append_filters',
  'l10n_ar_account_vat_ledger',
  'l10n_ar_account_vat_ledger_citi',
  'web_widget_domain_editor_dialog',
  'web_widget_image_url',
  'web_action_conditionable',
  'website_crm_recaptcha',
  'dbfilter_from_header',
  'datetime_formatter',
  'base_search_mail_content',
  'website_sale_require_legal',
  'quality_control_stock',
  'mrp_production_request',
  'mrp_stock_orderpoint_manual_procurement',
  'mrp_multi_level_estimate',
  'website_cookie_notice',
  'analytic_partner_hr_timesheet',
  'crm_claim_code',
  'stock_orderpoint_mrp_link',
  'purchase_stock_picking_restrict_cancel',
  'purchase_request_order_approved',
  'sale_order_product_recommendation_secondary_unit',
  'sale_automatic_workflow_payment_mode',
  # todavia no migrados
  'l10n_ar_sale',
  'web_search_with_and',
  'web_advanced_search',
  'website_media_size',
  'web_ir_actions_act_multi',
  'web_disable_export_group',
  'document_url',
]


xmlid_renames = [
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
  # ('saas_client.field_res_users__saas_provider_uuid', 'saas_client_adhoc.field_res_users__saas_provider_uuid'),
  ('saas_client.group_hidden_resources', 'saas_client_adhoc.group_hidden_resources'),
  ('saas_client.contract_adhoc_modules', 'saas_client_adhoc.contract_adhoc_modules'),
  ('saas_client.disable_inactive_users', 'saas_client_adhoc.disable_inactive_users'),
]
