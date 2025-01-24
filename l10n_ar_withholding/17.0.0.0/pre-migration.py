from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api


_column_copy = {
    'account_tax': [('withholding_sequence_id', 'withholding_sequence_id_bu', None)],
    'account_payment': [
        ('tax_withholding_id', 'tax_withholding_id_bu', None),
        ('withholding_number', 'withholding_number_bu', None),
        ('withholding_base_amount', 'withholding_base_amount_bu', None),
    ],
}


_field_renames = [
    ('account.tax', 'account_tax', 'withholding_sequence_id', 'l10n_ar_withholding_sequence_id'),
]


def migrate(cr, version):
    # backup de columnas que nos interesan antes de que se borren
    env = api.Environment(cr, SUPERUSER_ID, {})
    openupgrade.copy_columns(cr, _column_copy)
    openupgrade.rename_fields(env, _field_renames)
