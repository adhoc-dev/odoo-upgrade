
obsolte_modules = [
    # web_widget_color
    # PENDING MIGRATION pero que queremos depreciar
    # a este en realidad dijimos de tratar de no migrar
    'partner_views_fields',
    # dijimos que no tiene mucho sentido asi que lo borramos por ahora
    'account_user_default_journals',

    # no los queremos mas porque usamos saas_client
    'database_tools',
    'web_support_client',
    'web_support_client_issue',
    'web_support_server',
    'web_support_server_issue',
    'website_infrastructure_contract',
    'infrastructure_contract',
    'infrastructure_issue',

    # redpreciado, tal vez porque ordeneamos por ordne de producto en nuestro
    # saas?, al final lo restablecimos porque hay algunos que lo usan
    # 'account_contract_lines_sequence',

    # PENDING MIGRATION
    # 'mail_tracking_mass_mailing', ya migrado
    'mail_sent',
    'account_invoice_operation',
    'sale_commission',
    'website_sale_clear_line',
    'product_category_search',
    'web_menu_navbar_needaction',
    'base_debug4all',
    'sale_stock_commission',
    'hr_commission',
    'sale_invoice_operation',
    'product_standard_margin',
    'mrp_operations_extension',
    'quality_control',
    'account_asset_analytic',
    'quality_control_mrp',
    'quality_control_tolerance',
    'quality_control_claim',
    'quality_control_sale_stock',
    'hr_expense_invoice',
    'quality_control_stock',
    'project_task_portal_unfollow',
    'website_blog_facebook_comment',
    'mrp_production_estimated_cost',
    'mrp_operations_project',
    'mail_full_expand',
    'website_sale_promotion',
    'purchase_last_price_info',
    'website_product_share',
    'website_sale_product_legal',
    'website_sale_recently_viewed_products',
    'website_sale_add_to_cart',
    'web_ir_actions_act_window_none',
    'portal_sale_distributor',
    'portal_stock_distributor',
    'portal_account_distributor',
    'sale_multiple_invoice',
    'account_move_voucher',
    # este ahora si lo incorporamos
    # 'account_tax_settlement',
    'account_tax_settlement_withholding',
    'hr_sign_in_out_task',
    'website_sale_note',
    'web_widget_one2many_tags',
    'portal_fix',
    'report_aeroo_portal_fix',
    'portal_partner_fix',
    'account_journal_book',
    'web_advanced_search_wildcard',
    'web_advanced_search_x2x',
    'web_search_with_and',
    'web_favicon',
    'website_favicon',
    'website_server_mode',
    # lo borramos porque ya se instalo el que correspondes
    'partner_credit_limit',
    'mass_mailing_statistic_extra',
    # Verificar compatibilidad con enterprie
    'web_switch_company_warning',
    # 'auth_brute_force',

    # no compatible con enterprise
    'web_widget_float_formula',
    # 'web_widget_many2many_tags_multi_selection', ya instalable
    # 'web_widget_x2many_2d_matrix', ya instalable
    # 'web_widget_color', ya instalable

    # modulos depreciados varios
    'bi_invoice_company_currency',
    'mrp_hook',
    'sale_margin_percentage',
    'machine_manager_preventive',
    'admin_useful_groups',

    # modulos depreciados de odoomrp wip:
    'machine_manager',
    'machine_purchase',
    'mrp_project_link',
    'mrp_machine_relation',
    'mrp_production_qty_to_produce_info',

    # modulos depreciados de odoomrp utils:
    'stock_quants_shortcuts',
    'mrp_stock_quant_shortcut',
    'sale_stock_quant_shortcut',
    'purchase_stock_quant_shortcut',
    'mrp_bom_line_search_view',
    'mrp_bom_structure_show_child',

    # modulos depreciados de akretion:
    'partner_products_shortcut',
    'delivery_no_invoice_shipping',
    'stock_display_destination_move',
    'stock_display_sale_id',
    'account_invoice_groupby_commercial_partner',
    'account_invoice_sale_link',
    'account_move_line_filter_wizard',
    # si llega a dar error entonces deberiamos instalarlo en pre script
    # y dejar que luego se instale aca si algunmodulo lo agrega
    # 'account_usability',
    'partner_search',
    'purchase_usability_extension',
    'sale_line_product_required',
    'sale_usability_extension',
    'partner_products_shortcut',
    'account_invoice_margin',
    'account_invoice_margin_report',

    # este lo borramos pero en realidad fue un rename a stock_usability
    # como este ultimo ya venia instalado para todos, lo borramos total ya fue
    # actualizado
    'stock_product_move',

    # OBSOLETE (this module has no problem to loose data)
    # si migramos por ahora usamos enterprise y este modulo no es compatible
    'disable_odoo_online',
    # no lo usamos mas, integrado a web_support_client
    'portal_welcome_email_template',
    'auth_admin_passkey',
    # nativo en v9
    'website_sale_collapse_categories',
    'inter_company_move',
    # 'account_contract_lines_sequence',
    'sale_order_type_sale_journal',
    'product_price_currency_margin',
    'product_computed_list_price_taxes_included',
    'sale_contract_default',
    'account_security_modifications',
    'base_vat',
    # fue mergeado...
    # 'l10n_ar_bank_cbu',
    'product_computed_price_rule',
    'project_task_desc_html',
    'account_voucher',
    'sale_usability_extension',
    # 'stock_usability', no lo borramos porque le hicimos rename
    'web_shortcuts',
    'website_mail_snippet_table_edit',
    # 'bi_view_editor',
    'web_action_close_wizard_view_reload',
    'mis_builder_demo',
    'ir_export_extended_ept',
    'invoice_fiscal_position_update',
    'web_clean_navbar',
    'attachment_edit',
    'attachment_preview',
    'contract_show_invoice',
    'sale_usability_extension',
    # 'support_branding',
    # 'web_ir_actions_act_window_message',
    'web_recipients_uncheck',
    'web_cleditor_ept',
    'web_graph_sort',
    'contract_discount',
    # 'web_dashboard_tile',
    # 'web_easy_switch_company',
    'adhoc_base_setup',
    'adhoc_base_account',
    'adhoc_base_stock',
    'adhoc_base_sale',
    'adhoc_base_project',
    'adhoc_base_purchase',
    'adhoc_base_website',
    'adhoc_base_product',
    'project_adhoc_personalization',
    'purchase_prices_update',
    'timesheet_task',
    'hr_timesheet_task',
    # 'disable_openerp_online',
    'cron_run_manually',
    'project_task_delegate',
    'account_analytic_project',
    # modulos anteriores
    'purchase_line_defaults',
    'report_xls',
    'account_analytic_analysis_mods',
    'purchase_product_menu',
    'l10n_ar_account_followup',
    'account_journal_sequence',
    'account_allow_code_change',
    'account_contract_recurring_total',
    'product_bookstore',
    'account_transfer',
    'account_consolidation_company',
    'account_general_ledger_fix',
    'account_move_line_no_filter',
    'account_onchange_fix',
    'account_partner_account_summary',
    'account_partner_balance',
    'account_financial_report_webkit',
    'account_financial_report_webkit_xls',
    'account_statement_disable_invoice_import',
    # 'account_statement_move_import',
    'multi_store',
    'portal_account_summary',
    'account_multicompany_usability_withholding',
    'contract_multic_fix',
    'account_invoice_pricelist_discount',
    'account_invoice_report_partner_categ',
    'account_invoice_tax_auto_update',
    'account_sale_different_currency',
    'account_journal_payment_subtype',
    'account_voucher_contact',
    'account_voucher_fix',
    'account_voucher_manual_reconcile',
    'account_voucher_payline',
    'account_voucher_popup_print',
    'account_voucher_account_fix',
    'account_voucher_constraint',
    # al final lo renombramos (al final no)
    'account_voucher_double_validation',
    'account_voucher_multic_fix',
    'crm_partner_history',
    'crm_phonecall_extend',
    'crm_phonecall_type',
    'hr_sign_in_out_task',
    'hr_timesheet_project',
    'mrp_auto_prod',
    'calendar_done',
    'calendar_state',
    'mass_mailing_keep_archives',
    'l10n_ar_account_voucher',
    'l10n_ar_aeroo_receipt',
    'l10n_ar_base_vat',
    'l10n_ar_hide_receipts',
    'l10n_ar_invoice_receipt',
    'l10n_ar_account_check',
    'infrastructure_product',
    'auth_server_admin_passwd_passkey',
    'collector_test',
    'sale_stock_picking_back2draft',
    'web_fixed_headers',
    'web_hw_collector',
    'web_list_view_sticky',
    'web_menu_hide',
    'partner_employee',
    'partner_establishment',
    'partner_no_auto_search',
    'partner_search_by_ref',
    'partner_search_by_vat',
    'partner_source',
    'partner_vat_unique',
    'partner_views_fields_base_vat',
    'user_partner_is_employee',
    'product_uom_prices',
    'product_publichsed_sale_price',
    'product_uom_prices_currency',
    'product_force_create_variants',
    'product_no_auto_search',
    'product_pack_pos',
    'product_stock_location',
    'product_template_update_active',
    'sale_stock_product_sale_uom',
    'portal_project_issue_solutions',
    'project_issue_views_modifications',
    'project_long_term',
    'project_task_desc_html',
    'project_user_story',
    'portal_project_issue_create',
    'project_analytic_integration',
    'project_task_delegate',
    'project_task_order',
    'purchase_add_products_wizard',
    'purchase_ref_editable',
    'report_extended_voucher',
    # 'web_pdf_preview',
    'sale_pricelist_discount',
    'sales_to_sale_order',
    'sale_team_group',
    'stock_multic_fix',
    'stock_picking_locations',
    'stock_move_defaults',
    'stock_picking_driver',
    'stock_transfer_set_zero',
    'stock_transfer_lot_filter',
    'website_less',
    'website_portal_sale_taxes_included',
    'website_rate_product',
    'website_remove_product_legend',
    'website_sale_cart_preview_taxes_included',
    'website_sale_invoice_before_delivery',
    'website_search',
    'website_tracking',
    'web_snippet_extra',
    # ahora son desinstalados por l10n_ar_chart directamente
    # 'l10n_ar_chart_generic_tax_settlement',
    # 'l10n_ar_chart_generic_withholding',
]
