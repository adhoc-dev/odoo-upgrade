"""The crons of l10n_cl_edi_fix_send_dte, which saas_client_l10n_cl depends on from 20.

Reads what scripts/pre_odoo/190_200/020-l10n_cl_edi_send_dte_cron.py backed up on the old database.

In end-migration because the module is installed in this same -u, as a new dependency.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_cl_edi_send_dte_cron_bu"
OLD_CRON = "l10n_cl_edi.ir_cron_send_send"
SEND_CRON = "l10n_cl_edi_fix_send_dte.ir_cron_send_dte_to_sii"
PARTNER_CRON = "l10n_cl_edi_fix_send_dte.ir_cron_send_dte_to_partner"


def migrate(cr, version):
    _logger.info("Running end-migration of saas_client_l10n_cl for version %s", version)
    _disable_partner_cron(cr)
    _restore_send_cron(cr)
    # Its code calls a method that Odoo 20 removed.
    util.remove_record(cr, OLD_CRON)


def _disable_partner_cron(cr):
    # Emailing the DTEs accepted with objections is not part of our product. The record of
    # the module data does not reach an existing database: its xmlid is noupdate.
    cron_id = util.ref(cr, PARTNER_CRON)
    if not cron_id:
        _logger.warning("%s not found: l10n_cl_edi_fix_send_dte is not installed?", PARTNER_CRON)
        return
    cr.execute(SQL("UPDATE ir_cron SET active = false WHERE id = %s", cron_id))


def _restore_send_cron(cr):
    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.warning("No %s: the SII send cron keeps its default. Did the pre_odoo script run?", BACKUP_TABLE)
        return
    cr.execute(SQL("SELECT active, interval_number, interval_type, nextcall FROM %s", SQL.identifier(BACKUP_TABLE)))
    row = cr.fetchone()
    if not row:
        _logger.info("The SII send cron was not changed in 19: it keeps the default of %s", SEND_CRON)
        return
    cron_id = util.ref(cr, SEND_CRON)
    if not cron_id:
        _logger.warning("%s not found: the changed SII send cron of 19 is not restored", SEND_CRON)
        return
    active, interval_number, interval_type, nextcall = row
    cr.execute(
        SQL(
            """
            UPDATE ir_cron
               SET active = %s, interval_number = %s, interval_type = %s, nextcall = %s
             WHERE id = %s
            """,
            active,
            interval_number,
            interval_type,
            nextcall,
            cron_id,
        )
    )
    _logger.info(
        "Restored the SII send cron of 19 on %s: active=%s, every %s %s",
        SEND_CRON,
        active,
        interval_number,
        interval_type,
    )
