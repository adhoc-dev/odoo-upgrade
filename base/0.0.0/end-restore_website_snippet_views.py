"""Bring back, per website, the shop and login views with the state they had before the upgrade.

Reads what pre_odoo_scripts/always/080-backup_website_snippet_views.py backed up on the old
database. If the website copy is still there its state is set back; if not, the generic view is
copied for that website.

One savepoint per view: the upgrade line was left in draft once for breaking upgrades here, so
a view that fails is reported and the rest goes on.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_ui_view_website_snippet_bu"
# The upgrade line only ran on upgrades to 17.0 and later.
FIRST_TARGET_VERSION = 17


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no website views to restore", BACKUP_TABLE)
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if util.module_installed(cr, "website"):
        cr.execute(
            SQL(
                """
                SELECT bu.key, bu.website_id, bu.active
                  FROM %s bu
                  JOIN website w ON w.id = bu.website_id
                 ORDER BY bu.website_id, bu.key
                """,
                SQL.identifier(BACKUP_TABLE),
            )
        )
        rows = cr.fetchall()
        views = util.env(cr)["ir.ui.view"].with_context(active_test=False)
        updated, copied, failed = [], [], []
        for key, website_id, active in rows:
            label = "%s (website %s)" % (key, website_id)
            try:
                with cr.savepoint():
                    view = views.search([("key", "=", key), ("website_id", "=", website_id)], limit=1)
                    if view:
                        if view.active != active:
                            view.write({"active": active})
                            updated.append(label)
                        continue
                    base_view = views.search([("key", "=", key), ("website_id", "=", False)], limit=1)
                    if base_view:
                        base_view.copy(default={"website_id": website_id, "active": active, "key": key})
                        copied.append(label)
            except Exception as e:
                failed.append("%s (%s)" % (label, str(e)[:300]))
        if updated:
            _logger.info("Website views set back to their state: %s", ", ".join(updated))
        if copied:
            _logger.info("Website views copied again: %s", ", ".join(copied))
        if failed:
            _logger.warning("Website views that could not be restored: %s", "; ".join(failed))
