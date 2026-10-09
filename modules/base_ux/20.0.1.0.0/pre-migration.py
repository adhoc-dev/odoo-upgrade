import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """In 20.0 the activity type field uses the badges_many2one widget and base_ux
    adopts the native badges. Its old views look for selection_badge_icons, and while
    they stay in the database any module that validates those forms after base_ux
    (hr, calendar, phone_validation) breaks the update."""
    _logger.info("Removing base_ux quick activity badges views")
    util.remove_view(cr, "base_ux.mail_activity_schedule_view_form_inherit")
    util.remove_view(cr, "base_ux.mail_activity_view_form_popup_inherit")
