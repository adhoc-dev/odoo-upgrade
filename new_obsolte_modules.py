# estos son modulos que no deberian estar mas, borramos si estan desintalados con:
# env['ir.module.module'].search([('name', 'in', new_obsolete), ('state', 'in', ['uninstalled', 'uninstallable'])]).unlink()
new_obsolte_modules = [
    # modulos nuevos
    'logos_setup_data',
    'account_payment_order_to_voucher',
    'account_voucher_cash_basis',
    'account_voucher_display_writeoff',
    'account_voucher_supplier_invoice_number',
    'account_voucher_tax_filter',
    'hr_expense_analytic_plans',
    'account_cost_center',
    'account_invoice_supplierinfo_update_discount',
    'account_invoice_supplierinfo_update_variant',
    'hr_holidays_lunch_voucher_natixis',
    'account_analytic_plan_required',
    'analytic_multicurrency',
    'crm_timesheet',
    'hr_attendance_analysis',
    'hr_timesheet_activity_begin_end',
    # este es el que estaba mal escrito
    'account_mutlicompany_usability',
    'account_invoice_operation',
    'sale_invoice_operation',
    'hr_timesheet_fulfill',
    'invoice_margin',
    'hr_timesheet_holidays',
    'hr_timesheet_sheet_change_period',
    'partner_identification_gln',
    'sale_markup_group_user',
    'sale_line_price_properties_based',
    'stock_product_location_sorted_by_qty',
    'module_uninstall_check',
    'partner_tag_actions',
    'product_supplierinfo_for_customer_sale',
    'account_invoice_overdue_filter',
    'account_mutlicompany_usability_withholding',
    'account_refund_invoice_fix',
    'partner_noncommercial',
    'product_pricelist_cache',
    'profiler',
    'sale_comment_propagation',
    'purchase_supplier_rounding_method',
    'account_invoice_update_wizard',
    'account_invoice_pricelist_sale_stock',
    'product_disable_quick_create',
    'product_customer_price',
    'base_field_serialized',
    'account_invoice_pricelist_sale',
    'account_analytic_analysis_discount',
    'hr_timesheet_reminder',
    'hr_timesheet_print',
    'website_sale_clear_line',
    'printer_tray',
    'web_menu_navbar_needaction',
    'product_variant_multi',
    'product_variant_multi_advanced',
    'sale_journal_shop',
    'stock_filter_none_zero_qty',
    'logos_invoice_analysis',
    'odecon_sale_order_report',
    'product_simple_accounting',
    'product_unit_manager_group',
    'sale_line_quantity_properties_based',
    'sales_team_security',
    'stock_inventory_location',
    'website_hr_contact',
    'web_x2many_add_button_position',
    'stock_quant_partner_info',
    'sale_product_multi_add',
    'sale_fiscal_position_update',
    'anglo_saxon_dropshipping',
    'account_check_reports',
    'account_invoice_auto_pay',
    'crm_partner_area',
    'account_auto_fy_sequence',
    'snippet_latest_posts',
    'hr_timesheet_improvement',
    'hr_commission',
    'crm_lead_lost_reason',
    'sale_stock_commission',
    'website_event_register_free_with_sale',
    'website_event_register_free',
    'snippet_google_map',
    'theme_notes',
    'theme_kiddo_sale',
    'theme_graphene',
    'theme_clean',
    'theme_loftspace',
    'theme_loftspace_sale',
    'theme_treehouse',
    'theme_avantgarde',
    'theme_zap',
    'theme_beauty',
    'theme_beauty_sale',
    'theme_anelusia',
    'theme_anelusia_sale',
    'theme_enark',
    'theme_kea_sale',
    'theme_odoo_experts',
    'theme_odoo_experts_sale',
    'theme_bistro',
    'theme_orchid_sale',
    'theme_bewise',
    'theme_bookstore_sale',
    'theme_bookstore',
    'theme_monglia',
    'theme_monglia_sale',
    'theme_nano',
    'theme_notes_sale',
    'theme_kiddo',
    'theme_vehicle',
    'theme_vehicle_sale',
    'theme_artists',
    'theme_artists_sale',
    'theme_real_estate',
    'theme_real_estate_sale',
    'theme_yes',
    'theme_yes_sale',
    # modulos anteriores
    'logos_product_attributes',
    'logos_dependencies',
    'product_cost_currency',
    'product_pack_discount',
    'analytic_surveyor',
    'surveyor',
    'surveyor_payments',
    'account_analytic_and_plans',
    'account_bank_statement_import_usability',
    'account_compute_tax_amount',
    'account_direct_debit_autogenerate',
    'account_fiscal_position_translate',
    'account_invoice_del_attachment_cancel',
    'account_invoice_groupby_commercial_partner',
    'account_invoice_line_stock_move_info',
    'account_invoice_line_wave_info',
    'account_invoice_partner_bank_usability',
    'account_invoice_picking_label',
    'account_invoice_sale_link',
    'account_invoice_supplier_number_info',
    'account_invoice_supplier_ref_required',
    'account_move_line_start_end_dates_xls',
    'account_netting',
    'account_payment_force_maturity_date',
    'account_payment_hide_communication2',
    'account_payment_security',
    'account_security_modifications',
    'account_tax_report_no_zeroes',
    'account_voucher_default_amount',
    'aeroo_report_to_printer',
    'analytic_production_cost_report',
    'attachment_metadata',
    'base_company_extension',
    'base_concurrency',
    'base_contact',
    'base_debug4all',
    'base_fix_display_address',
    'base_ir_filters_active',
    'base_module_doc_rst',
    'base_other_report_engines',
    'base_partner_always_multi_contacts',
    'base_usability',
    'base_user_reset_access',
    'calendar_default_value',
    'connector',
    'connector_base_product',
    'contract_commission',
    'contract_invoice_merge_by_partner',
    'contract_payment_mode',
    'contract_recurring_plans',
    'contract_show_recurring_invoice',
    'crm_claim_extra_ref',
    'crm_claim_ref_search',
    'crm_deduplicate_by_website',
    'crm_lead_firstname',
    'crm_lead_invoice_address',
    'crm_lead_marketing_info',
    'crm_lead_second_lastname',
    'crm_lead_supplier',
    'crm_lead_vat',
    'crm_phonecall_category',
    'crm_phonecall_summary_predefined',
    'crm_sector',
    'dead_mans_switch_server',
    'delivery_no_invoice_shipping',
    'delivery_partner_properties',
    'document_page_partner_id',
    'document_page_tags',
    'eradicate_quick_create',
    'field_char_transformed',
    'hr_expense_usability',
    'hr_holidays_usability',
    'hr_usability',
    'invoice_fiscal_position_update',
    'l10n_eu_product_adr_report',
    'l10n_fr_fix_thousands_sep',
    'l10n_fr_infogreffe_connector',
    'l10n_fr_usability',
    'log_forwarded_for_ip',
    'mail_follower_custom_notification',
    'mail_footer_notified_partners',
    'mail_forward',
    'mail_mandrill',
    'mail_read_new_window',
    'mail_sent',
    'mail_template_multi_report',
    'mrp_export_field_profile',
    'mrp_lock_lot',
    'mrp_production_unreserve_movements',
    'mrp_stock_info',
    'mrp_stock_quant_shortcut',
    'mrp_usability',
    'partner_academic_title',
    'partner_address_type_default',
    'partner_aged_open_invoices',
    'partner_capital',
    'partner_employee_quantity',
    'partner_group',
    'partner_second_lastname',
    'passport',
    'phone_directory_report',
    'picking_dispatch',
    'pos_journal_sequence',
    'pos_no_product_template_menu',
    'pos_sale_report',
    'pos_usability',
    'pricelist_per_product',
    'procurement_jit_assign_move',
    'procurement_manager',
    'procurement_suggest',
    'procurement_suggest_purchase',
    'procurement_usability',
    'product_category_in_header',
    'product_category_tax',
    'product_expiry_ext',
    'product_export_field_profile',
    'product_m2mcategories',
    'product_manager_group',
    'product_manager_group_stock',
    'product_packaging_views',
    'product_pricelist_partnerinfo',
    'product_profile',
    'product_profile_example',
    'product_stock_info',
    'product_supplierinfo_for_customer',
    'product_type',
    'product_unique_serial',
    'product_uom_change_fix',
    'product_usability',
    'product_variant_csv_import',
    'project_issue_extension',
    'purchase_auto_invoice_method',
    'purchase_order_copy_bid_origin',
    'purchase_order_line_form_button',
    'purchase_order_line_stock_available',
    'purchase_pricelist_partnerinfo',
    'purchase_stock_quant_shortcut',
    'purchase_usability_extension',
    'qweb_usertime',
    'report_qweb_signer',
    'report_xml',
    'report_xml_sample',
    'sale_line_product_required',
    'sale_margin_no_onchange',
    'sale_margin_report',
    'sale_order_add_variants',
    'sale_order_back2draft',
    'sale_order_line_form_button',
    'sale_partner_incoterm',
    'sale_payment_method',
    'sale_payment_method_automatic_workflow',
    'sale_properties_dynamic_fields',
    'sale_properties_easy_creation',
    'sale_purchase_no_product_template_menu',
    'sale_stock_picking_back2draft',
    'sale_stock_quant_shortcut',
    'sale_stock_show_delivery_address',
    'sale_stock_usability',
    'save_translation_file',
    'shell',
    'social_media_dribbble',
    'social_media_tripadvisor',
    'social_media_xing',
    'stock_account_usability',
    'stock_display_destination_move',
    'stock_display_sale_id',
    'stock_incoterm_extension',
    'stock_invoice_try_again',
    'stock_lock_lot',
    'stock_lot_note',
    'stock_lot_scrap',
    'stock_move_partner_info',
    'stock_my_operations_filter',
    'stock_no_negative',
    'stock_picking_carrier',
    'stock_picking_customer_ref',
    'stock_picking_invoicing_incoterm',
    'stock_picking_invoicing_incoterm_sale',
    'stock_picking_package_preparation_add_to_wave',
    'stock_picking_type_default_partner',
    'stock_picking_visible_scheduled_date',
    'stock_planning',
    'stock_planning_mrp',
    'stock_planning_procurement_generated_by_plan',
    'stock_planning_rule',
    'stock_quant_reservation_status',
    'stock_quants_shortcuts',
    'stock_quant_stock_info',
    'stock_transfer_continue_later',
    'users_ldap_push',
    'web_analytics',
    'web_eradicate_duplicate',
    'web_ir_actions_act_window_none',
    'web_listview_show_advanced_search',
    'web_offline_warning',
    'web_one2many_list_action',
    'web_search_autocomplete_prefetch',
    'web_search_datetime_completion',
    'website_country_localized_pages',
    'website_crm_address',
    'website_crm_quick_answer',
    'website_crm_sales_team',
    'website_event_filter_organizer',
    'website_mail_snippet_bg_color',
    'website_mail_snippet_fixed',
    'website_mail_snippet_responsive',
    'website_mail_snippet_vertical_resize_base',
    'website_mass_mailing_name',
    'website_signup_legal_page_required',
    'website_snippet_contact_form',
    'web_widget_digitized_signature',
    'web_widget_digitized_signature_user',
    'web_widget_radio_tree',
    'web_search_drawer_unfold',
    'document_page_extension',
    'help_doc',
    'help_doc_account',
    'help_doc_crm',
    'help_doc_mail',
    'help_doc_multi_company',
    'help_doc_project',
    'help_doc_project_issue',
    'help_doc_purchase',
    'help_doc_sale',
    'help_doc_stock',
    'access_apps',
    'access_apps_website',
    'access_base',
    'access_limit_records_number',
    'access_menu_extra_groups',
    'access_restricted',
    'access_settings_menu',
    'app_store',
    'app_store_client',
    'auth_oauth_check_client_id',
    'auth_oauth_ip',
    'base_report_designer',
    'birth_date_age',
    'crm_custom_fields',
    'crm_profiling',
    'account_contract_project',
    'newsletter_email_template_qweb',
    'base_debug4all',
    'base_title_on_partner',
    'crm_timesheet_analytic_partner',
    'csv_import_upload_migrate',
    'account_move_usability',
    'document_fs',
    'document_page_adhoc',
    'erd_maker',
    'exam_test_quiz',
    'expresso_product_attributes',
    'form_image_preview',
    'group_menu_no_access',
    'help_doc_portal',
    'hidden_admin',
    'hr_timesheet_invoice_hide_to_invoice',
    'hr_timesheet_invoice_hide_to_invoice_task',
    'hr_timesheet_no_closed_project_task',
    'html_form_builder',
    'html_form_builder_campaign',
    'html_form_builder_email',
    'html_form_builder_snippets',
    'ir_mail_server_per_user',
    'ir_rule_protected',
    'mail_campaign_survey',
    'mass_image_upload',
    'module_overview',
    'oauth_provider',
    'openupgrade_records',
    'portal_expresso',
    'product_price_factor',
    'product_price_factor_online',
    'res_users_clear_access_rights',
    'runbot',
    'runbot_cla',
    'runbot_selftest',
    'runbot_send_email',
    'runbot_travis2docker',
    'saas_base',
    # 'saas_client',
    'saas_multi_db_campaign',
    'saas_portal',
    'saas_portal_backup',
    'saas_portal_demo',
    'saas_portal_demo_example',
    'saas_portal_portal',
    'saas_portal_sale',
    'saas_portal_sale_online',
    'saas_portal_signup',
    'saas_portal_start',
    'saas_portal_tagging',
    'saas_portal_templates',
    'saas_server',
    'saas_server_autodelete',
    'saas_server_backup_ftp',
    'saas_server_backup_rotate',
    'saas_server_backup_rotate_s3',
    'saas_server_backup_s3',
    'saas_support',
    'saas_sysadmin',
    'saas_sysadmin_aws',
    'saas_sysadmin_aws_route53',
    'saas_sysadmin_mailgun',
    'saas_sysadmin_route53',
    'saas_utils',
    'sms_frame',
    'sms_frame_calendar_alarm',
    'sms_frame_mail_campaign',
    'sms_frame_twilio',
    'united_backend_theme',
    'website_calendar_booking',
    'website_custom_pricelist',
    'website_dating',
    'website_multi',
    'website_style_manager',
    'website_support',
    'website_template_pages',
    'website_vacuum_cart',
    'base_import_async',
    'product_category_search',
    'mail_print',
    'mrp_bom_line_search_view',
    'mrp_bom_structure_show_child',
    'mrp_production_qty_to_produce_info',
    'product_variant_weight',
    'purchase_suggest_min_qty_on_product',
    'website_product_share',
    'website_sale_collapse_categories',
    'website_snippet_marginless_gallery',
    'web_widget_mail_send_odoo',
    'website_product_filters',
    'inter_company_move',
    'theme_orchid',
    'sale_order_mail_product_attachment',
    'sale_order_mail_product_attach_prod_pack',
    'mail_notification_email_template',
    'mrp_show_related_attachment',
    'partner_products_shortcut',
    'procurement_analytic',
    'product_variant_cost_price',
    'purchase_procurement_analytic',
    'website_product_show_uom',
    'website_sale_cart_preview',
    'website_sale_product_legal',
    'sale_add_products_wizard',
    'sale_contract_default',
    'stock_product_move',
    'website_issue_form',
    'account_credit_control_usability',
    'account_cutoff_accrual_picking_ods',
    'account_cutoff_prepaid_ods',
    'account_due_list_aging_comments',
    'account_due_list_days_overdue',
    'account_fiscal_position_payable_receivable',
    'account_fiscal_year_reopen',
    'account_hide_analytic_line',
    'account_invoice_line_price_subtotal_gross',
    'account_invoice_margin',
    'account_invoice_margin_report',
    'account_move_line_filter_wizard',
    'account_move_line_import',
    'account_payment_extension',
    'account_payment_order_sequence',
    'account_payment_return',
    'account_payment_return_import',
    'account_payment_return_import_sepa_pain',
    'account_reconcile_trace',
    'account_voucher_source_document',
    'attribute_usability',
    'base_field_validator',
    'base_location_lau',
    'contract',
    'contract_account_banking_mandate',
    'contract_journal',
    'contract_recurring_invoicing_marker',
    'contract_recurring_invoicing_monthly_last_day',
    'contract_show_invoice',
    'contract_variable_quantity',
    'crm_autoalias',
    'crm_deduplicate_filter',
    'crm_usability',
    'document_ocr',
    'document_rtf_index',
    'document_sftp',
    'field_rrule',
    'hr_employee_no_welcome',
    'hr_expense_product_policy',
    'hr_payroll_cancel',
    'hr_payslip_change_state',
    'hr_timesheet_task_required',
    'intrastat_product_type',
    'l10n_account_translate',
    'l10n_fr_intrastat_product_ods',
    'mail_usability',
    'mass_mailing_event',
    'mass_mailing_sending_queue',
    'module_usability',
    'mrp_analytic',
    'mrp_bom_version',
    'mrp_hook',
    'mrp_operations_extension',
    'mrp_operations_project',
    'mrp_operations_start_without_material',
    'mrp_operations_time_control',
    'mrp_produce_uos',
    'mrp_production_estimated_cost',
    'mrp_production_real_cost',
    'mrp_project',
    'mrp_repair_discount',
    'mrp_work_orders_calendar',
    'partner_create_by_vat',
    'partner_product_variants_shortcut',
    'partner_search',
    'pos_analytic_by_config',
    'pos_second_ean13',
    'pricelist_item_generator',
    'procurement_mrp_no_confirm',
    'product_analytic',
    'product_attribute_priority',
    'product_code_builder',
    'product_code_builder_sequence',
    'product_cost_utilities',
    'product_custom_info',
    'product_filters',
    'product_margin_classification',
    'product_standard_price_tax_included',
    'product_variant_available_in_pos',
    'product_variant_inactive',
    'product_variant_sale_price',
    'product_variant_search_by_attribute',
    'purchase_add_product_supplierinfo',
    'purchase_commercial_partner',
    'purchase_date_planned_update',
    'purchase_hide_report_print_menu',
    'purchase_line_product_required',
    'purchase_order_line_description',
    'purchase_order_manual_close',
    'purchase_payment',
    'purchase_requisition_type',
    'purchase_rfq_number',
    'quality_control',
    'quality_control_force_valid',
    'quality_control_mrp',
    'quality_control_stock',
    'sale_allotment',
    'sale_automatic_workflow_exception',
    'sale_change_price',
    'sale_commission',
    'mass_mailing_partner',
    'estudios_integrales_modifications',
    'product_scanterra_extension',
    'project_issue_kretz_custom',
    'scanterra_modifcations',
    'stock_product_orderpoint',
    'web_support_server_doc',
    'account_analytic_analysis_usability',
    'account_asset_depr_line_cancel',
    'account_invoice_direct_payment',
    'account_invoice_kanban',
    'account_invoice_supplierinfo_update',
    'account_invoice_supplierinfo_update_on_validate',
    'base_import_security_group',
    'base_mail_bcc',
    'business_product_location',
    'crespo_personalization',
    'hr_holidays_lunch_voucher',
    'customer_pricing_in_product_view',
    'partner_split_menu',
    'product_expiry_simple',
    'product_variant_usability',
    'pxgo_cash_statement',
    'nan_account_bank_statement',
    'pxgo_bank_statement_analytic',
    'mass_mailing_unique',
    'pxgo_bank_statement_running_balance',
    'resource_usability',
    'sale_order_weight',
    'sale_other_product_description',
    'sql_request_abstract',
    'sale_partner_shipping_filter_with_customer',
    'salveregina_picking_report',
    'stock_inventory_hierarchical_location',
    'stock_account_change_product_valuation',
    'stock_orderpoint_creator',
    'stock_picking_backorder_to_sale',
    'web_x2m_defaults_from_previous',
    'wetcom_personalization',
    'web_popup_large',
    'web_color',
    # themes?
    # 'theme_bewise',
    # 'theme_bookstore',
    # 'theme_bookstore_sale',
    # 'theme_yes_sale',
    'sale_commission_formula',
    'sale_commission_product',
    'sale_crm_usability',
    'sale_no_filter_myorder',
    'sale_order_calendar_event',
    'sale_order_line_price_subtotal_gross',
    'sale_order_line_variant_description',
    'sale_order_manual_close',
    'sale_order_merge',
    'sale_order_route',
    'sale_order_type_sale_journal',
    'sale_order_unified_menu',
    'sale_payment',
    'sale_payment_method_transaction_id',
    'sale_quick_payment',
    'sale_quotation_title',
    'sale_service_fleet',
    'sale_service_project',
    'sale_stock_auto_move',
    'secure_uninstall',
    'stock_analytic',
    'stock_auto_move',
    'stock_change_qty_reason',
    'stock_inventory_hierarchical',
    'stock_inventory_line_price',
    'stock_inventory_lockdown',
    'stock_inventory_valuation_ods',
    'stock_landed_cost_analytic',
    'stock_lot_quantity',
    'stock_operation_type_location',
    'stock_picking_invoice_product_group',
    'stock_picking_invoicing_unified',
    'stock_picking_manual_procurement_group',
    'stock_picking_mass_action',
    'stock_picking_zip',
    'stock_route_sales_team',
    'stock_scanner',
    'stock_traceability_operation',
    'test_base_import_async',
    'web_hideleftmenu',
    'web_invalid_tab',
    'web_menu_autohide',
    'website_blog_excerpt_img',
    'website_blog_title_image',
    'website_calendar_snippet',
    'website_hr_directory',
    'website_multi_image',
    'website_parameterized_snippet',
    'website_product_supplier',
    'website_sale_cart_selectable',
    'website_sale_checkout_comment',
    'website_sale_product_category_seo',
    'website_sale_survey',
    'website_supplier_list',
    'website_upload_video',
    'web_widget_pattern',
    'web_x2m_filter',
]
