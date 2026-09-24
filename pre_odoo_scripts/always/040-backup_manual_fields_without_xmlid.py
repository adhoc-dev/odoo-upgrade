import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-drop_generated_manual_field_xmlids.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_model_fields_no_xmlid_bu"


def migrate(cr, version):
    """Back up which custom (manual) fields have no xmlid before the database is sent to Odoo.

    The Odoo upgrade gives them one, and the customization counter then stops counting them
    as interface customizations. The upgrade line it replaces read them from the old database to drop those xmlids.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    _logger.info("Backing up the manual fields without xmlid into %s", BACKUP_TABLE)

    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT f.id
              FROM ir_model_fields f
             WHERE f.state = 'manual'
               AND NOT EXISTS (SELECT 1
                                 FROM ir_model_data d
                                WHERE d.model = 'ir.model.fields'
                                  AND d.res_id = f.id)
        """
        % BACKUP_TABLE
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
