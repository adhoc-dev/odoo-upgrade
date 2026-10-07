import logging

from oba import log_message, should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 2370.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Archive the sales team memberships of the admin user before the database is sent to Odoo.

    The admin is the archived support user: as a team member, an Odoo test of the upgrade
    fails on access rights. The user is found by its xmlid, base.user_admin.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_run_pre_odoo(cr, FIRST_TARGET_VERSION):
        return

    # The upgrade line did not filter by module; without sales_team there is no table.
    cr.execute("SELECT to_regclass('crm_team_member')")
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        UPDATE crm_team_member m
           SET active = false
          FROM ir_model_data d
         WHERE d.module = 'base'
           AND d.name = 'user_admin'
           AND d.model = 'res.users'
           AND m.user_id = d.res_id
           AND m.active
     RETURNING m.id
        """
    )
    archived = cr.rowcount
    if archived:
        log_message(cr, "Archived %d crm.team.member record(s) for the admin user" % archived, "info")
    else:
        log_message(cr, "No active crm.team.member records found for the admin user, nothing to do", "info")
