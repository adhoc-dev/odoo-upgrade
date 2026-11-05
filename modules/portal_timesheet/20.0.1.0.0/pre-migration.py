import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

XMLIDS = [
    "portal_timesheet.account_analytic_account_timesheet_portal_backend_user_access",
    "portal_timesheet.account_analytic_line_timesheet_portal_backend_user",
]


def migrate(cr, version):
    """Let the -u load these two records from security/ir.access.csv.

    In 19 they were ir.rule records of a noupdate file, on
    portal_backend.group_portal_backend. In 20 the module declares them as
    ir.access on group_portal_backend_timesheet, merged with the ACLs. If the
    upgrade of Odoo keeps the xmlids with noupdate, the -u skips the csv and the
    records stay as the upgrade left them.
    """
    for xmlid in XMLIDS:
        _logger.info("Removing noupdate from %s", xmlid)
        util.force_noupdate(cr, xmlid, noupdate=False)
