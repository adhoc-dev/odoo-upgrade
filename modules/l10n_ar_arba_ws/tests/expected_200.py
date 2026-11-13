"""l10n_ar_arba_ws 19 -> 20: the ARBA certificate and DDJJ of the withholdings already informed.

| 19 (l10n_ar.payment.withholding) | 20 (account.payment.withholding.line) |
| --- | --- |
| l10n_ar_cert_number, l10n_ar_dj_arba_id | the same, on the line l10n_ar_tax made of it (l10n_ar_payment_withholding_map_bu) |
| informed line that l10n_ar_tax did not move | warning only, with the old ids |

modules/l10n_ar_arba_ws/tests/test_certificates_to_20.py tests the script case by case.
"""

NO_CHECK = (
    "The withholding lines are created by the migration of l10n_ar_tax, without xmlid, so no expected can point "
    "to them; the SQL test next to this file covers the script."
)
