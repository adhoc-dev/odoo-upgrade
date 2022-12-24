renamed_modules = {
    'report_pdf_preview': 'prt_report_attachment_preview',
    'crm_stage_teams': 'crm_teams_ux',
    'account_bank_statement_import_txt_xlsx': 'account_statement_import_txt_xlsx',
}


merged_modules = {
    'product_reference_required': 'product_code_mandatory',
    'account_payment_fix': 'account_ux',
    'account_payment_group_document': 'account_payment_group',
    'project_stage': 'project_ux',
    # como este modulo ya viene en odoo 16 y viene indexado, si hacemos rename da error. Otra alternativa seria borra el registro de latam
    # antes de llamar al rename, pero asi va bien
    'account_check': 'l10n_latam_check',
}


xmlid_renames = [
    ('product_reference_required.sequence', 'product_code_mandatory.product_default_code_seq'),
    ('l10n_latam_check.account_payment_method_issue_check', 'account_check_printing.account_payment_method_check'),
]
