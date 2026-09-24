"""Drop the xmlids that the upgrade generated for custom (manual) fields.

Reads what pre_odoo_scripts/always/040-backup_manual_fields_without_xmlid.py backed up on the
old database. Without it, the customization counter stops counting those fields as interface
customizations.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import json
import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_model_fields_no_xmlid_bu"
# Written by the runner for the whole -u; same key as odoo.upgrade.oba.request_context.
REQUEST_CONTEXT_PARAMETER = "saas_upgrade.request_context"


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (REQUEST_CONTEXT_PARAMETER,))
    row = cr.fetchone()
    context = json.loads(row[0]) if row and row[0] else None
    # The upgrade line only ran on test requests. Without context (runbot, a local -u) it runs.
    if context is not None and context.get("aim") != "test":
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Its pre_odoo script always backs up: in a provider run, no table means it did not run.
        log = _logger.warning if context is not None else _logger.info
        log("No %s: no generated xmlids to drop", BACKUP_TABLE)
        return

    # Kept only when a module now defines the field: that module owns its xmlid.
    cr.execute(
        SQL(
            """
            DELETE FROM ir_model_data d
             USING %s bu
              LEFT JOIN ir_model_fields f ON f.id = bu.id
             WHERE d.model = 'ir.model.fields'
               AND d.res_id = bu.id
               AND (f.id IS NULL OR f.state = 'manual')
         RETURNING d.module || '.' || d.name, d.res_id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    dropped = sorted(cr.fetchall(), key=lambda row: row[1])
    if dropped:
        _logger.info("Dropped the xmlids the upgrade generated for manual fields: %s", dropped)
