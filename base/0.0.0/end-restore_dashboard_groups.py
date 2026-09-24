"""Put back the groups the standard dashboards had before the upgrade.

Reads what pre_odoo_scripts/always/070-backup_dashboard_group_xmlids.py backed up on the old
database.

Dashboards and groups are matched by xmlid. A dashboard whose groups are all gone keeps the
ones the upgrade gave it, as the upgrade line did.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "spreadsheet_dashboard_group_xmlid_bu"
# The upgrade line only ran on upgrades to 18.0 and later.
FIRST_TARGET_VERSION = 18
REL_TABLE = "res_groups_spreadsheet_dashboard_rel"


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no dashboard groups to restore", BACKUP_TABLE)
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if util.table_exists(cr, REL_TABLE):
        cr.execute(
            SQL(
                """
                WITH old AS (
                    SELECT dd.res_id AS dashboard_id, array_agg(DISTINCT g.id ORDER BY g.id) AS group_ids
                      FROM %s bu
                      JOIN ir_model_data dd ON dd.model = 'spreadsheet.dashboard'
                                           AND dd.module = bu.dashboard_module
                                           AND dd.name = bu.dashboard_name
                      JOIN spreadsheet_dashboard d ON d.id = dd.res_id
                      JOIN ir_model_data gd ON gd.model = 'res.groups'
                                           AND gd.module = bu.group_module
                                           AND gd.name = bu.group_name
                      JOIN res_groups g ON g.id = gd.res_id
                     GROUP BY dd.res_id
                )
                SELECT old.dashboard_id, old.group_ids
                  FROM old
                 WHERE old.group_ids IS DISTINCT FROM (SELECT array_agg(rel.res_groups_id ORDER BY rel.res_groups_id)
                                                         FROM %s rel
                                                        WHERE rel.spreadsheet_dashboard_id = old.dashboard_id)
                """,
                SQL.identifier(BACKUP_TABLE),
                SQL.identifier(REL_TABLE),
            )
        )
        restored = []
        for dashboard_id, group_ids in cr.fetchall():
            cr.execute(
                SQL("DELETE FROM %s WHERE spreadsheet_dashboard_id = %s", SQL.identifier(REL_TABLE), dashboard_id)
            )
            cr.execute(
                SQL(
                    "INSERT INTO %s (spreadsheet_dashboard_id, res_groups_id) SELECT %s, unnest(%s)",
                    SQL.identifier(REL_TABLE),
                    dashboard_id,
                    group_ids,
                )
            )
            restored.append(dashboard_id)
        if restored:
            _logger.info("Restored the groups of the dashboards %s", sorted(restored))
