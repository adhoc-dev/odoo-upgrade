import json
import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-restore_active_crons.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_cron_active_bu"
# Written by the runner before the scripts run; same key as odoo.upgrade.oba.request_context.
REQUEST_CONTEXT_PARAMETER = "saas_upgrade.request_context"


def migrate(cr, version):
    """Back up which crons are active before the database is sent to Odoo.

    The upgrade line it replaces read them from the old database by RPC
    to re-activate the ones that end up inactive after the upgrade.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Only on the last request of a series, as the upgrade line with execution_position.
    # Without a request context (outside a provider run) it runs.
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (REQUEST_CONTEXT_PARAMETER,))
    row = cr.fetchone()
    if row and row[0] and not json.loads(row[0]).get("is_last_in_series", True):
        _logger.info("Not the last request of the series: the crons are handled there")
        return

    _logger.info("Backing up the active crons into %s", BACKUP_TABLE)

    cr.execute("CREATE TABLE %s AS SELECT id FROM ir_cron WHERE active" % BACKUP_TABLE)
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
