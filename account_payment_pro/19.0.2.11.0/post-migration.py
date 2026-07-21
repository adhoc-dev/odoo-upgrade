import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# account.payment.method.line codes that require a cuenta de liquidez
# (l10n_latam_check_ux/models/account_payment.py: check_inbound_codes | check_outbound_codes)
_CHECK_METHOD_CODES = [
    "new_third_party_checks",
    "own_checks",
    "issued_checks",
    "in_third_party_checks",
    "out_third_party_checks",
    "return_third_party_checks",
]


def migrate(cr, version):
    _logger.info("Running post-migration for version %s", version)

    env = util.env(cr)
    payments = env["account.payment"].search(
        [
            ("outstanding_account_id", "=", False),
            ("payment_method_line_id.code", "in", _CHECK_METHOD_CODES),
            ("payment_method_line_id.payment_account_id", "!=", False),
        ]
    )
    _logger.info(
        "Backfilling outstanding_account_id on %s check payments", len(payments)
    )
    payments.invalidate_recordset(["outstanding_account_id"])
    payments.modified(["payment_method_line_id"])
    payments.flush_recordset(["outstanding_account_id"])
