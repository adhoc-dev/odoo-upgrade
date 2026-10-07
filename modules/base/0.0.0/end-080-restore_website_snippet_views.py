"""Bring back, per website, the shop and login views with the state they had before the upgrade.

Reads what scripts/pre_odoo/always/080-backup_website_snippet_views.py backed up on the old
database. If the website copy is still there its state is set back; if not, the generic view is
copied for that website.

One savepoint per view: the upgrade line was left in draft once for breaking upgrades here, so
a view that fails is reported and the rest goes on.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_ui_view_website_snippet_bu"
# Upgrades to 19 still run the upgrade line; same floor as the pre_odoo script.
FIRST_TARGET_VERSION = 20
# Inactive copies of a broken customization; the post upgrade line 884 deletes them.
NOT_UPGRADE_COPY = ("name", "not ilike", "(Copy created during upgrade)")


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    if not should_run(cr, version, FIRST_TARGET_VERSION):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no website views to restore", BACKUP_TABLE)
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
                    view = views.search(
                        [("key", "=", key), ("website_id", "=", website_id), NOT_UPGRADE_COPY], limit=1
                    )
                    if view:
                        if view.active != active:
                            view.write({"active": active})
                            updated.append(label)
                        continue
                    base_view = views.search(
                        [("key", "=", key), ("website_id", "=", False), NOT_UPGRADE_COPY], limit=1
                    )
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
            log_message(cr, "Website views that could not be restored: %s" % "; ".join(failed), "warning")
