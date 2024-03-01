from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


_column_copy = {
    'account_tax': [('withholding_sequence_id', 'withholding_sequence_id_bu', None)],
    'account_payment': [
        ('payment_group_id', 'payment_group_id_bu', None),
        ('tax_withholding_id', 'tax_withholding_id_bu', None),
        ('withholding_number', 'withholding_number_bu', None),
        ('withholding_base_amount', 'withholding_base_amount_bu', None),
        ('automatic', 'automatic_bu', None),
        ('withholdable_invoiced_amount', 'withholdable_invoiced_amount_bu', None),
        ('withholdable_advanced_amount', 'withholdable_advanced_amount_bu', None),
        ('accumulated_amount', 'accumulated_amount_bu', None),
        ('total_amount', 'total_amount_bu', None),
        ('withholding_non_taxable_minimum', 'withholding_non_taxable_minimum_bu', None),
        ('withholding_non_taxable_amount', 'withholding_non_taxable_amount_bu', None),
        ('withholdable_base_amount', 'withholdable_base_amount_bu', None),
        ('period_withholding_amount', 'period_withholding_amount_bu', None),
        ('previous_withholding_amount', 'previous_withholding_amount_bu', None),
        ('computed_withholding_amount', 'computed_withholding_amount_bu', None),
    ],
}


_table_renames = [
    ('account_payment_group', 'account_payment_group_bu'),
    ('account_payment_receiptbook', 'account_payment_receiptbook_bu'),
    ('account_move_line_payment_group_to_pay_rel', 'account_move_line_payment_group_to_pay_rel_bu'),
]


_field_renames = [
    ('account.tax', 'account_tax', 'withholding_sequence_id', 'l10n_ar_withholding_sequence_id'),
]


@openupgrade.migrate()
def migrate(env, version):
    # backup de columnas que nos interesan antes de que se borren
    openupgrade.copy_columns(env.cr, _column_copy)
    # backup de tables y checkbooks
    for old_table, new_table in _table_renames:
        if openupgrade.table_exists(env.cr, old_table):
            openupgrade.rename_tables(env.cr, [(old_table, new_table)])

    # Add temporary table for avoiding the automatic launch of the compute method
    openupgrade.logged_query(
        env.cr, "CREATE TABLE account_move_line_payment_to_pay_rel (temp INTEGER)",
    )

    openupgrade.rename_fields(env, _field_renames)
