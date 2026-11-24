import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Mark the "Other Expenses" accounts as not monetary.

    is_monetary is a stored compute, so adding expense_other to the non-monetary
    types in 20 does not fix the accounts that come from 19 with is_monetary set.
    """
    _logger.info("Running account_ux post-migration for version %s", version)
    cr.execute(
        SQL(
            """
            UPDATE account_account
               SET is_monetary = FALSE
             WHERE account_type = %(account_type)s
               AND is_monetary
            """,
            account_type="expense_other",
        )
    )
    _logger.info("Marked %s other expenses accounts as not monetary", cr.rowcount)
