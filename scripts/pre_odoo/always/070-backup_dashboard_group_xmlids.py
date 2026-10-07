import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-070-restore_dashboard_groups.py, on the other side of the upgrade.
BACKUP_TABLE = "spreadsheet_dashboard_group_xmlid_bu"
# Upgrades to 19 still run the upgrade line; same floor as the consumer.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the groups of the standard dashboards, by xmlid, before the database is sent to Odoo.

    The upgrade resets them to the ones in the module data. The upgrade line it replaces read them from the old database to put the original ones back.

    By xmlid on both sides because the ids of the groups are not stable across the upgrade.
    A group without xmlid cannot be found on the other side, so it is left out, as the
    upgrade line did.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["spreadsheet_dashboard"]):
        return

    _logger.info("Backing up the groups of the standard dashboards into %s", BACKUP_TABLE)
    create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT DISTINCT dd.module AS dashboard_module,
                        dd.name AS dashboard_name,
                        gd.module AS group_module,
                        gd.name AS group_name
          FROM res_groups_spreadsheet_dashboard_rel rel
          JOIN ir_model_data dd ON dd.model = 'spreadsheet.dashboard'
                               AND dd.res_id = rel.spreadsheet_dashboard_id
          JOIN ir_model_data gd ON gd.model = 'res.groups'
                               AND gd.res_id = rel.res_groups_id
        """,
        primary_key=("dashboard_module", "dashboard_name", "group_module", "group_name"),
    )
