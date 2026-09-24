"""Restore the `related` that the upgrade left empty on the custom (manual) fields.

Reads what pre_odoo_scripts/always/030-backup_manual_related_fields.py backed up on the old
database.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "ir_model_fields_related_bu"
# Written by the runner for the whole -u; same key as odoo.upgrade.oba.request_context.
REQUEST_CONTEXT_PARAMETER = "saas_upgrade.request_context"


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Its pre_odoo script always backs up: in a provider run, no table means it did not run.
        cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = %s", (REQUEST_CONTEXT_PARAMETER,))
        log = _logger.warning if cr.fetchone() else _logger.info
        log("No %s: no related fields to restore", BACKUP_TABLE)
        return

    # state = manual: an id that became a base field in the new version cannot be written.
    cr.execute(
        SQL(
            """
            SELECT bu.id, bu.model, bu.name, bu.related
              FROM %s bu
              JOIN ir_model_fields f ON f.id = bu.id
             WHERE f.state = 'manual'
               AND COALESCE(f.related, '') = ''
             ORDER BY bu.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    rows = cr.fetchall()
    if rows:
        fields_model = util.env(cr)["ir.model.fields"]
        fixed, failed = [], []
        for field_id, model, name, related in rows:
            label = "%s.%s -> %s" % (model, name, related)
            # By ORM, like the upgrade line: the write validates the related, and SQL would leave
            # a broken one for the next registry load.
            try:
                with cr.savepoint():
                    fields_model.browse(field_id).write({"related": related})
                fixed.append(label)
            except Exception as e:
                # May come from a customization: keep the upgrade going and report it.
                failed.append("%s (%s)" % (label, str(e)[:300]))
        if fixed:
            _logger.info("Restored related: %s", ", ".join(fixed))
        if failed:
            _logger.warning("Related that could not be restored: %s", "; ".join(failed))
