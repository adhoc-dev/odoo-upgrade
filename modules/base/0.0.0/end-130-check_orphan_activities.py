"""Warn about the activities whose document no longer exists.

Only a warning, as the upgrade line: the integrations team fixes them by ticket.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

# Upgrades to 19 still run the upgrade line 1470.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["mail"]):
        return

    cr.execute(
        """
        SELECT res_model, array_agg(DISTINCT res_id)
          FROM mail_activity
         WHERE active
           AND res_model IS NOT NULL
           AND res_id IS NOT NULL
         GROUP BY res_model
         ORDER BY res_model
        """
    )
    orphans = []
    for model, res_ids in cr.fetchall():
        table = util.table_of_model(cr, model)
        found = 0
        if util.table_exists(cr, table):
            cr.execute(SQL("SELECT COUNT(*) FROM %s WHERE id = ANY(%s)", SQL.identifier(table), res_ids))
            found = cr.fetchone()[0]
        if found != len(res_ids):
            orphans.append("%s: target=%s, qty=%s" % (table, len(res_ids), found))
    if orphans:
        log_message(cr, "Activities linked to documents that no longer exist: %s" % orphans, "warning")
