from odoo.upgrade import util


def migrate(cr, version):
    if util.column_exists(cr, 'account_tax', 'codigo_regimen'):
        util.rename_field(cr, 'account.tax', 'codigo_regimen', 'l10n_ar_code')
