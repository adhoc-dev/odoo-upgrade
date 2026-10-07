import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-030-restore_manual_related_fields.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_model_fields_related_bu"
# Upgrades to 19 still run the upgrade line; same floor as the consumer.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the `related` of the custom (manual) fields before the database is sent to Odoo.

    The Odoo upgrade can leave it empty. The upgrade line it replaces read it
    from the old database by RPC to restore it.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION):
        return

    _logger.info("Backing up the related of the manual fields into %s", BACKUP_TABLE)
    create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, model, name, related
          FROM ir_model_fields
         WHERE state = 'manual'
           AND COALESCE(related, '') != ''
        """,
    )
