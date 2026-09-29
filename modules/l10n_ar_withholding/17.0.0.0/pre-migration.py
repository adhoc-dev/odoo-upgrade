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

    # Hay casos de impuestos que pertenecen a una compañía pero la secuencia de dicho impuesto
    # (l10n_ar_withholding_sequence_id) pertenece a otra compañía.
    # Lo que hacemos en esta query es establecerle a la secuencia la misma compañía que la compañía del impuesto.
    openupgrade.logged_query(
        env.cr,
            """
            UPDATE ir_sequence SET company_id = atax.company_id
            FROM account_tax atax
            WHERE atax.l10n_ar_withholding_sequence_id = ir_sequence.id AND atax.company_id IN
                (SELECT rc.id FROM res_company AS rc
                JOIN res_partner AS rp ON rc.partner_id = rp.id
                JOIN res_country AS c ON rp.country_id = c.id
                WHERE c.code = 'AR')
            AND atax.company_id != ir_sequence.company_id
            AND ir_sequence.company_id IS NOT NULL;
            """
    )
