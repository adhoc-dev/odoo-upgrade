import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # The auto-close reminder is new in 20 and is born on for every team. Up to 19 no team sent
    # it: keep it off, the closing notice already goes in the stage emails.
    if not util.column_exists(cr, "helpdesk_team", "auto_close_ticket_reminder"):
        return
    cr.execute(
        """
        UPDATE helpdesk_team
           SET auto_close_ticket_reminder = FALSE
         WHERE auto_close_ticket_reminder IS TRUE
        """
    )
    _logger.info(
        "Turned off auto_close_ticket_reminder on %s helpdesk teams", cr.rowcount
    )
