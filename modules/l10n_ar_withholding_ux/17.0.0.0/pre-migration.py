from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


_column_copy = {
    'account_payment': [
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


@openupgrade.migrate()
def migrate(env, version):
    # backup de columnas que nos interesan antes de que se borren
    openupgrade.copy_columns(env.cr, _column_copy)
