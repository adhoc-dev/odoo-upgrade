import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

UNPAID_CATEGORIES = (
    "unpaid_info_category",
    "unpaid_warning_category",
    "unpaid_danger_category",
    "unpaid_suspended_category",
)

REMOVED_FIELDS = [
    ("sale.order", "communication_id"),
    ("sale.order", "do_not_suspend_before"),
    ("sale.order", "suspend_date"),
    ("sale.subscription.plan", "unpaid_days_info"),
    ("sale.subscription.plan", "unpaid_days_warning"),
    ("sale.subscription.plan", "unpaid_days_danger"),
    ("sale.subscription.plan", "unpaid_days_suspend"),
]


def migrate(cr, version):
    """Remove the unpaid invoices communications, deprecated in 20.

    The cron and the categories are noupdate data, so the -u keeps them. The
    server action of the cron goes after the cron, which restricts its deletion.
    The communications go before their categories: their category is required.
    """
    _logger.info("Removing the unpaid invoices communications")
    for model, field in REMOVED_FIELDS:
        util.remove_field(cr, model, field)

    util.remove_record(cr, "saas_provider_adhoc.unpaid_invoices_cron")
    util.remove_record(cr, "saas_provider_adhoc.unpaid_invoices_cron_ir_actions_server")

    cr.execute(
        SQL(
            """
            SELECT c.id
              FROM saas_communication c
              JOIN ir_model_data d
                ON d.model = 'saas.communication.category'
               AND d.res_id = c.category_id
             WHERE d.module = 'saas_provider_adhoc'
               AND d.name IN %(names)s
            """,
            names=UNPAID_CATEGORIES,
        )
    )
    communication_ids = [row[0] for row in cr.fetchall()]
    _logger.info("Removing %s unpaid invoices communications", len(communication_ids))
    util.remove_records(cr, "saas.communication", communication_ids)

    for name in UNPAID_CATEGORIES:
        util.remove_record(cr, f"saas_provider_adhoc.{name}")
