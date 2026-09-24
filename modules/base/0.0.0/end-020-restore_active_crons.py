"""Re-activate the crons that were active before the upgrade.

Reads what scripts/pre_odoo/always/020-backup_active_crons.py backed up on the old database.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, request_context

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_cron_active_bu"
# Upgrades to 19 still run the upgrade line; same floor as the pre_odoo script.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Its pre_odoo script backs up on the last request of a provider run: no table there
        # means it did not run.
        context = request_context(cr)
        message = "No %s: no crons to re-activate" % BACKUP_TABLE
        if context and context.get("is_last_in_series", True):
            log_message(cr, message, "warning")
        else:
            _logger.info(message)
        return

    cr.execute(
        SQL(
            """
            UPDATE ir_cron c
               SET active = true
              FROM %s bu
             WHERE c.id = bu.id
               AND NOT c.active
         RETURNING c.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    cron_ids = sorted(row[0] for row in cr.fetchall())
    if cron_ids:
        _logger.info("Re-activated %s crons that were active before the upgrade: %s", len(cron_ids), cron_ids)
