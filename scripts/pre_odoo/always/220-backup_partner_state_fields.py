import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-220-check_partner_state_fields.py, on the other side of the upgrade.
BACKUP_TABLE = "res_partner_state_field_bu"
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the partner_state configuration lines before the database is sent to Odoo.

    Each line points to a res.partner field with ON DELETE CASCADE: when the upgrade drops
    that field, the line goes with it and the approval rule is lost with no error.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["partner_state"]):
        return

    _logger.info("Backing up the partner state fields into %s", BACKUP_TABLE)
    create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT s.id, f.name AS field_name,
               COALESCE(f.field_description->>'es_419', f.field_description->>'en_US', f.name) AS field_label,
               s.approval, s.block_edition, s.track, s.changes
          FROM res_partner_state_field s
          JOIN ir_model_fields f ON f.id = s.field_id
        """,
    )
