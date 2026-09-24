import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-restore_manual_related_fields.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_model_fields_related_bu"


def migrate(cr, version):
    """Back up the `related` of the custom (manual) fields before the database is sent to Odoo.

    The Odoo upgrade can leave it empty. The upgrade line it replaces read it
    from the old database by RPC to restore it.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    _logger.info("Backing up the related of the manual fields into %s", BACKUP_TABLE)

    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
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
