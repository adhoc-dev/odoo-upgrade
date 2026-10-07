import logging

from oba import log_message, should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 1689.
FIRST_TARGET_VERSION = 20
# The portal-backend family: internal users cannot keep any of them.
PORTAL_BACKEND_GROUPS = (
    ("portal_backend", "group_portal_backend"),
    ("portal_timesheet", "group_portal_backend_timesheet"),
    ("portal_holidays", "group_portal_backend_holiday"),
    ("portal_sale_distributor", "group_portal_backend_distributor"),
    ("portal_sale_distributor", "group_portal_backend_distributor_stock"),
)


def migrate(cr, version):
    """Leave each user in a single user type group before the database is sent to Odoo.

    A user can be internal, portal or public, not more than one. An internal user loses
    portal, public and the portal-backend groups; a portal user loses public. The users
    fixed go to the request, so a later failure for this reason is easy to trace.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_run_pre_odoo(cr, FIRST_TARGET_VERSION, modules=["portal_backend"]):
        return

    cr.execute(
        """
        SELECT name, res_id
          FROM ir_model_data
         WHERE module = 'base'
           AND model = 'res.groups'
           AND name IN ('group_user', 'group_portal', 'group_public')
        """
    )
    groups = dict(cr.fetchall())
    internal, portal, public = groups.get("group_user"), groups.get("group_portal"), groups.get("group_public")
    if not (internal and portal and public):
        _logger.info("The base user type groups are not all there: nothing to fix")
        return

    cr.execute(
        "SELECT res_id, module || '.' || name FROM ir_model_data WHERE model = 'res.groups' AND (module, name) IN %s",
        (PORTAL_BACKEND_GROUPS,),
    )
    labels = dict(cr.fetchall())
    labels.update({portal: "base.group_portal", public: "base.group_public"})
    to_remove = list(labels)

    cr.execute(
        """
        SELECT u.login, conflict.gid
          FROM res_users u
          JOIN res_groups_users_rel internal ON internal.uid = u.id AND internal.gid = %s
          JOIN res_groups_users_rel conflict ON conflict.uid = u.id AND conflict.gid = ANY(%s)
         ORDER BY u.login, conflict.gid
        """,
        (internal, to_remove),
    )
    conflicts = cr.fetchall()
    if conflicts:
        log_message(
            cr,
            "\n".join(
                "Usuario interno '%s' pertenecía al grupo '%s' (se lo quitamos)" % (login, labels[gid])
                for login, gid in conflicts
            ),
            "warning",
        )

    cr.execute(
        """
        DELETE FROM res_groups_users_rel
         WHERE gid = ANY(%s)
           AND uid IN (SELECT uid FROM res_groups_users_rel WHERE gid = %s)
        """,
        (to_remove, internal),
    )
    cr.execute(
        """
        DELETE FROM res_groups_users_rel
         WHERE gid = %s
           AND uid IN (SELECT uid FROM res_groups_users_rel WHERE gid = %s)
        """,
        (public, portal),
    )
