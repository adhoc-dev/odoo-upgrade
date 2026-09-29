from odoo.upgrade import util


def migrate(cr, version):
    if util.column_exists(cr, 'account_tax', 'codigo_regimen'):
        util.rename_field(cr, 'account.tax', 'codigo_regimen', 'l10n_ar_code')
    if util.column_exists(cr, 'account_tax', 'withholding_non_taxable_minimum'):
        util.rename_field(cr, 'account.tax', 'withholding_non_taxable_minimum', 'l10n_ar_payment_minimum_threshold')
    if util.column_exists(cr, 'account_tax', 'withholding_non_taxable_amount'):
        util.rename_field(cr, 'account.tax', 'withholding_non_taxable_amount', 'l10n_ar_base_minimum_threshold')
