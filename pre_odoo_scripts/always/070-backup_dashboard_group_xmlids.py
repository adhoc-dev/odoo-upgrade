import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-restore_dashboard_groups.py, on the other side of the upgrade.
BACKUP_TABLE = "spreadsheet_dashboard_group_xmlid_bu"


def migrate(cr, version):
    """Back up the groups of the standard dashboards, by xmlid, before the database is sent to Odoo.

    The upgrade resets them to the ones in the module data. The upgrade line it replaces read them from the old database to put the original ones back.

    By xmlid on both sides because the ids of the groups are not stable across the upgrade.
    A group without xmlid cannot be found on the other side, so it is left out, as the
    upgrade line did.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Only with spreadsheet_dashboard installed, like the upgrade line; the version gate is in the consumer.
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'spreadsheet_dashboard' AND state = 'installed'")
    if not cr.fetchone():
        return

    _logger.info("Backing up the groups of the standard dashboards into %s", BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT DISTINCT dd.module AS dashboard_module,
                            dd.name AS dashboard_name,
                            gd.module AS group_module,
                            gd.name AS group_name
              FROM res_groups_spreadsheet_dashboard_rel rel
              JOIN ir_model_data dd ON dd.model = 'spreadsheet.dashboard'
                                   AND dd.res_id = rel.spreadsheet_dashboard_id
              JOIN ir_model_data gd ON gd.model = 'res.groups'
                                   AND gd.res_id = rel.res_groups_id
        """
        % BACKUP_TABLE
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute(
        "ALTER TABLE %s ADD PRIMARY KEY (dashboard_module, dashboard_name, group_module, group_name)"
        % BACKUP_TABLE
    )
