"""l10n_ar_tax 19 -> 20: the withholding lines go to account.payment.withholding.line.

| 19 (l10n_ar.payment.withholding, ARS) | 20 (account.payment.withholding.line, payment currency) |
| --- | --- |
| payment_id, tax_id, name, ref | the same |
| base_amount, amount | x accounting_rate of the payment (payment currency per ARS) |
| base_amount, amount | also as they are in l10n_ar_base_amount, l10n_ar_amount (ARS) |
| - | account_id: tax line of the payment entry, or the tax repartition account |
| account.payment.amount (net) | net + withholdings; amount_exact and counterpart_currency_amount follow |
| AR tax that is not a withholding, with a withholding type | type cleaned: in 20 it cannot be saved with one |
| AR purchase earnings withholding without l10n_ar_code | warning only: the code is not guessed |
| account.tax l10n_ar_state_id (AR taxes) | account.tax.group l10n_ar_state_id, when all the taxes of the group agree |
| account.tax withholding_sequence_id (supplier withholdings) | account.tax.group withholding_sequence_id, when they agree |
| AR tax without value, in a group that has one | takes the value of its group |
| AR tax that is not a supplier withholding, with a sequence | loses it |
| taxes of a group with different values | warning only: the group stays empty, the value is not chosen |

modules/l10n_ar_tax/tests/test_withholding_lines_to_20.py tests the post-migration case by case, and
modules/l10n_ar_tax/tests/test_tax_groups_to_20.py the pre-migration.
"""

NO_CHECK = (
    "The withholding lines are created by the migration, without xmlid, so no expected can point to them; "
    "and the gross amount of the payment combines the 19 amount with the sum of its lines. The tax groups "
    "of the chart are scoped by company id, which changes from one test base to another, and their "
    "sequences have no xmlid. All of it is out of the declarative checks; the SQL tests next to this file "
    "cover them."
)
