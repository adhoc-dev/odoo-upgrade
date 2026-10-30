import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move the payment tolerance of the reconcile models to the native one of 20.

    In 19 the module added `payment_tolerance` as an amount. In 20 the standard has the same
    column, read as a percentage unless `payment_tolerance_type` says otherwise, and only the
    matching rules (`rule_type`) apply it, which are always automatic.

    - automatic models with a tolerance become matching rules, in amount
    - manual models cannot be matching rules, so they keep working as reconcile models without
      tolerance, and are listed for the team
    """
    if not util.column_exists(cr, "account_reconcile_model", "rule_type"):
        _logger.info("account_reconcile_model has no rule_type: nothing to move")
        return

    cr.execute(
        SQL(
            """
            UPDATE account_reconcile_model
               SET rule_type = 'matching_rule',
                   payment_tolerance_type = 'amount'
             WHERE payment_tolerance > 0
               AND "trigger" = 'auto_reconcile'
               AND rule_type IS DISTINCT FROM 'matching_rule'
            """
        )
    )
    _logger.info("Converted %s automatic reconcile models with tolerance to matching rules", cr.rowcount)

    cr.execute(
        SQL(
            """
            UPDATE account_reconcile_model
               SET payment_tolerance = 0
             WHERE payment_tolerance > 0
               AND "trigger" IS DISTINCT FROM 'auto_reconcile'
         RETURNING id, COALESCE(name ->> 'en_US', name::text), payment_tolerance_type
            """
        )
    )
    for model_id, name, _tolerance_type in cr.fetchall():
        log_message(
            cr,
            "The manual reconcile model %r (id %s) had a payment tolerance, which in 20 only the "
            "automatic matching rules have. It keeps working without tolerance." % (name, model_id),
            "warning",
            module="account_statement_base_ux",
        )
