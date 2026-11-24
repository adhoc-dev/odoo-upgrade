import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

XMLIDS = [
    "portal_timesheet.account_analytic_account_timesheet_portal_backend_user_access",
    "portal_timesheet.account_analytic_line_timesheet_portal_backend_user",
]

# ACLs of 19 without domain that the module no longer declares
REMOVED_XMLIDS = [
    "portal_timesheet.portal_timesheet_project_task",
    "portal_timesheet.portal_timesheet_account_analytic_line",
    "portal_timesheet.portal_timesheet_account_analytic_account",
]


def migrate(cr, version):
    """Let the -u load these two records from security/ir.access.csv, and drop the old ACLs.

    In 19 they were ir.rule records of a noupdate file, on
    portal_backend.group_portal_backend. In 20 the module declares them as
    ir.access on group_portal_backend_timesheet, merged with the ACLs. If the
    upgrade of Odoo keeps the xmlids with noupdate, the -u skips the csv and the
    records stay as the upgrade left them.

    The ACLs of 19 had no domain, and in 20 the accesses of a group add up: if
    one stays, the group reads and writes every task, timesheet and analytic
    account.
    """
    for xmlid in XMLIDS:
        _logger.info("Removing noupdate from %s", xmlid)
        util.force_noupdate(cr, xmlid, noupdate=False)
    for xmlid in REMOVED_XMLIDS:
        _logger.info("Removing %s", xmlid)
        util.remove_record(cr, xmlid)
