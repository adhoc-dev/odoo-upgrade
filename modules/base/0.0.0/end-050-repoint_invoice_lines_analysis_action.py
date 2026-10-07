"""Repoint the custom dashboards from "Invoice Lines Analysis" to "Invoices Analysis".

Reads what scripts/pre_odoo/always/050-backup_invoice_lines_analysis_actions.py backed up on
the old database. A custom dashboard points to its actions by id, and the old action is gone in
18.0.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_actions_invoice_lines_analysis_bu"
# Upgrades to 19 still run the upgrade line; same floor as the pre_odoo script.
FIRST_TARGET_VERSION = 20
NEW_NAMES = ["Invoices Analysis", "Análisis de facturas"]


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    if not should_run(cr, version, FIRST_TARGET_VERSION):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no dashboards to repoint", BACKUP_TABLE)
        return

    cr.execute(SQL("SELECT id FROM %s", SQL.identifier(BACKUP_TABLE)))
    old_ids = [row[0] for row in cr.fetchall()]
    env = util.env(cr)
    views = env["ir.ui.view.custom"].search([("arch", "ilike", "action")]) if old_ids else []
    if views:
        new_action = env["ir.actions.actions"].search([("name", "in", NEW_NAMES)], limit=1)
        if not new_action:
            log_message(
                cr, "There are old action ids, but no new Invoices Analysis action: nothing repointed", "warning"
            )
        else:
            repointed, failed = [], []
            for view in views:
                arch = view.arch
                for old_id in old_ids:
                    arch = arch.replace('name="%s"' % old_id, 'name="%s"' % new_action.id)
                if arch == view.arch:
                    continue
                # One dashboard that fails must not stop the -u, as it did not stop the upgrade line.
                try:
                    with cr.savepoint():
                        view.write({"arch": arch})
                    repointed.append(view.id)
                except Exception as e:
                    failed.append("%s (%s)" % (view.id, str(e)[:300]))
            if repointed:
                _logger.info("Repointed to action %s the custom dashboards %s", new_action.id, repointed)
            if failed:
                log_message(cr, "Custom dashboards that could not be repointed: %s" % "; ".join(failed), "warning")
