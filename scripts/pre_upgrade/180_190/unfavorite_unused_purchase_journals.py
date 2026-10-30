import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the dashboard favorite from unused purchase journals.

    The accounting dashboard fires one call per favorite journal, so databases with many
    companies hit the rate limit when opening it. A purchase journal that is a favorite,
    was created more than a year ago and has no entries is just noise.
    """
    _logger.info("Running pre-upgrade script 'unfavorite_unused_purchase_journals' for version %s", version)

    if not util.column_exists(cr, "account_journal", "show_on_dashboard"):
        return

    cr.execute(
        """
        UPDATE account_journal j
           SET show_on_dashboard = FALSE
         WHERE j.type = 'purchase'
           AND j.show_on_dashboard
           AND j.create_date < now() - interval '1 year'
           AND NOT EXISTS (SELECT 1 FROM account_move m WHERE m.journal_id = j.id)
        """
    )
    _logger.info("Removed the dashboard favorite from %s unused purchase journals", cr.rowcount)
