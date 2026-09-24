import logging
import re

from oba import request_context

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
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Upgrades to 19 still run the upgrade line. The target comes in the request context; a
    # provider that does not send it only upgrades to 19. Outside a provider run it backs up.
    context = request_context(cr)
    target = re.search(r"\d+", context.get("to_version") or "")
    if context and (not target or int(target.group()) < FIRST_TARGET_VERSION):
        _logger.info("Not an upgrade to %s or later: the upgrade line handles it", FIRST_TARGET_VERSION)
        return

    _logger.info("Backing up the related of the manual fields into %s", BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT id, model, name, related
              FROM ir_model_fields
             WHERE state = 'manual'
               AND COALESCE(related, '') != ''
        """
        % BACKUP_TABLE
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
