import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Up to 19 the "Don't Send Stage Email" toggle stayed on when the ticket moved to a stage
    # without an email template, and then skipped the email of a later stage. In 20 any stage
    # change turns it off: start from a clean state so no ticket skips its next stage email.
    if not util.column_exists(cr, "helpdesk_ticket", "dont_send_stage_email"):
        return
    cr.execute(
        """
        UPDATE helpdesk_ticket
           SET dont_send_stage_email = FALSE
         WHERE dont_send_stage_email IS TRUE
        """
    )
    _logger.info("Turned off dont_send_stage_email on %s tickets", cr.rowcount)
