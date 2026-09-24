"""Write on each subscription plan the sale_subscription_ux fields its recurring template had.

Reads what pre_odoo_scripts/always/090-backup_subscription_template_fields.py backed up on the
old database. In 17.0 the recurring sale.order.template becomes a sale.subscription.plan with
the same id.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "sale_order_template_subscription_bu"
# The upgrade line only ran on upgrades to 17.0 and later.
FIRST_TARGET_VERSION = 17
# plan field <- backup column
FIELDS = {
    "end_dates_required": "dates_required",
    "add_period_dates_to_description": "add_period_dates_to_description",
    "invoicing_method": "invoicing_method",
}


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no subscription plans to complete", BACKUP_TABLE)
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    env = util.env(cr)
    if "sale.subscription.plan" in env:
        plans = env["sale.subscription.plan"]
        fields = {name: column for name, column in FIELDS.items() if name in plans._fields}
        missing = sorted(set(FIELDS) - set(fields))
        if missing:
            _logger.warning("sale.subscription.plan has no %s: not completed on the plans", missing)
        if fields:
            cr.execute(
                SQL(
                    "SELECT id, %s FROM %s ORDER BY id",
                    SQL(", ").join(SQL.identifier(column) for column in fields.values()),
                    SQL.identifier(BACKUP_TABLE),
                )
            )
            written, failed, not_found = [], [], []
            for row in cr.fetchall():
                plan = plans.browse(row[0]).exists()
                if not plan:
                    not_found.append(row[0])
                    continue
                # One plan that fails (a required field left empty, say) must not stop the -u.
                try:
                    with cr.savepoint():
                        plan.write(dict(zip(fields, row[1:])))
                    written.append(plan.id)
                except Exception as e:
                    failed.append("%s (%s)" % (plan.id, str(e)[:300]))
            if written:
                _logger.info("Wrote the recurring template fields on the subscription plans %s", written)
            if failed:
                _logger.warning("Subscription plans that could not be completed: %s", "; ".join(failed))
            if not_found:
                _logger.warning("Recurring templates without a subscription plan: %s", not_found)
