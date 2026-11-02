import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/saas_client_l10n_cl/20.0.1.0.0/end-migration.py, on the other side of the pass.
BACKUP_TABLE = "l10n_cl_edi_send_dte_cron_bu"
TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the cron that sends the pending DTEs to the SII, when the client changed it.

    Odoo 20 drops l10n_cl_edi.ir_cron_send_send, and saas_client_l10n_cl now depends on
    l10n_cl_edi_fix_send_dte, which brings its own cron with another xmlid. Only a cron that
    is inactive or runs at another interval than the default of 19 (once a day) is backed up:
    the others take the default of the new cron.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_back_up(cr, BACKUP_TABLE, TARGET_VERSION, TARGET_VERSION, modules=["saas_client_l10n_cl"]):
        return

    count = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT c.id, c.active, c.interval_number, c.interval_type, c.nextcall
          FROM ir_cron c
          JOIN ir_model_data d
            ON d.model = 'ir.cron'
           AND d.res_id = c.id
         WHERE d.module = 'l10n_cl_edi'
           AND d.name = 'ir_cron_send_send'
           AND (NOT c.active OR c.interval_number <> 1 OR c.interval_type <> 'days')
        """,
    )
    _logger.info("Backed up %s changed SII send cron into %s", count, BACKUP_TABLE)
