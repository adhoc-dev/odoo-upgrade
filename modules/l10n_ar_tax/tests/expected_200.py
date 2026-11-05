"""l10n_ar_tax 19 -> 20: the withholding lines go to account.payment.withholding.line.

| 19 (l10n_ar.payment.withholding, ARS) | 20 (account.payment.withholding.line, payment currency) |
| --- | --- |
| payment_id, tax_id, name, ref | the same |
| base_amount, amount | x accounting_rate of the payment (payment currency per ARS) |
| - | account_id: tax line of the payment entry, or the tax repartition account |
| account.payment.amount (net) | net + withholdings; amount_exact and counterpart_currency_amount follow |

modules/l10n_ar_tax/tests/test_withholding_lines_to_20.py tests the script case by case.
"""

NO_CHECK = (
    "The withholding lines are created by the migration, without xmlid, so no expected can point to them; "
    "and the gross amount of the payment combines the 19 amount with the sum of its lines. Both are out "
    "of the declarative checks; the SQL test next to this file covers them."
)
