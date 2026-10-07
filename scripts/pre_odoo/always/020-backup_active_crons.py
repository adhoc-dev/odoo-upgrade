import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-020-restore_active_crons.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_cron_active_bu"
# Upgrades to 19 still run the upgrade line; same floor as the consumer.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up which crons are active before the database is sent to Odoo.

    The upgrade line it replaces read them from the old database by RPC
    to re-activate the ones that end up inactive after the upgrade.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, position="last"):
        return

    _logger.info("Backing up the active crons into %s", BACKUP_TABLE)

    create_backup(cr, BACKUP_TABLE, "SELECT id FROM ir_cron WHERE active")
