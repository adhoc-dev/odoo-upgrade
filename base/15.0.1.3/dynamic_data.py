renamed_modules = {
    # WIP
    # 'account_check': 'l10n_latam_check',
}


merged_modules = {
    'product_reference_required': 'product_code_mandatory',
    'account_payment_fix': 'account_ux',
    'account_payment_group_document': 'account_payment_group',
}


xmlid_renames = [
    ('product_reference_required.sequence', 'product_code_mandatory.product_default_code_seq'),
]
