"""Re-activate the crons that were active before the upgrade.

Reads what pre_odoo_scripts/always/020-backup_active_crons.py backed up on the old database.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import json
import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_cron_active_bu"
# Written by the runner for the whole -u; same key as odoo.upgrade.oba.request_context.
REQUEST_CONTEXT_PARAMETER = "saas_upgrade.request_context"


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Its pre_odoo script backs up on the last request of a provider run: no table there
        # means it did not run.
        cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (REQUEST_CONTEXT_PARAMETER,))
        row = cr.fetchone()
        expected = bool(row and row[0] and json.loads(row[0]).get("is_last_in_series", True))
        log = _logger.warning if expected else _logger.info
        log("No %s: no crons to re-activate", BACKUP_TABLE)
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
