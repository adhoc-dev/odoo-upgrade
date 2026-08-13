import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# In 18.0 hr_contract declares two groups. The upgrade renames the xmlid of the employee manager
# into the hr module (with noupdate) and drops the one of the "Administrator" group while keeping
# the record, so the group arrives without an xmlid and the personalization counter bills it as a
# customization of the client.
#
# The group is resolved through the ACL that hr_contract granted only to it: its model survives in
# 19.0, so the row and its xmlid reach this script still pointing at the group. The module load of
# the same -u all repoints that ACL to hr.group_hr_manager, which is what leaves the group with no
# structural trace afterwards: this script runs in the only window where the group is identifiable.
ANCHOR_NAME = "access_hr_payroll_structure_type_hr_contract_manager"
TWIN_NAME = "group_hr_contract_employee_manager"
GHOST_MODULE, GHOST_NAME = "hr", "group_hr_contract_manager"
# The merge of hr_contract into hr is done by the platform, before this script.
ANCHOR_MODULES = ["hr", "hr_contract"]


def migrate(cr, version):
    _logger.info("Running 'hr_contract_orphan_group' script for version %s", version)

    cr.execute(
        SQL(
            """
            SELECT acl.group_id
              FROM ir_model_data data
              JOIN ir_model_access acl ON acl.id = data.res_id
             WHERE data.model = 'ir.model.access'
               AND data.module = ANY(%(anchor_modules)s)
               AND data.name = %(anchor_name)s
               AND acl.group_id IS NOT NULL
               AND NOT EXISTS (SELECT 1
                                 FROM ir_model_data d
                                WHERE d.model = 'res.groups'
                                  AND d.res_id = acl.group_id)
               AND NOT EXISTS (SELECT 1
                                 FROM ir_model_data d
                                WHERE d.module = %(ghost_module)s
                                  AND d.name = %(ghost_name)s)
            """,
            anchor_modules=ANCHOR_MODULES,
            anchor_name=ANCHOR_NAME,
            ghost_module=GHOST_MODULE,
            ghost_name=GHOST_NAME,
        )
    )
    ghost_ids = [group_id for (group_id,) in cr.fetchall()]

    if len(ghost_ids) == 1:
        cr.execute(
            SQL(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                           create_date, write_date, create_uid, write_uid)
                     VALUES (%(module)s, %(name)s, 'res.groups', %(res_id)s, true,
                             now(), now(), 1, 1)
                """,
                module=GHOST_MODULE,
                name=GHOST_NAME,
                res_id=ghost_ids[0],
            )
        )
        _logger.info("Restored xmlid %s.%s for group %s", GHOST_MODULE, GHOST_NAME, ghost_ids[0])
    elif ghost_ids:
        # Never write on ambiguity: repairing the wrong group hides a real personalization.
        _logger.warning("ACL %s points to several groups without xmlid %s, skipping", ANCHOR_NAME, ghost_ids)
    else:
        # A miss must be loud: the previous version of this script matched the group by id
        # contiguity and silently did nothing on every base that installed hr_contract before 17.0.
        cr.execute(
            SQL(
                """
                SELECT EXISTS (SELECT 1 FROM ir_model_data
                                WHERE model = 'res.groups' AND name = %(twin_name)s),
                       EXISTS (SELECT 1 FROM ir_model_data
                                WHERE module = %(ghost_module)s AND name = %(ghost_name)s)
                """,
                twin_name=TWIN_NAME,
                ghost_module=GHOST_MODULE,
                ghost_name=GHOST_NAME,
            )
        )
        twin_exists, already_repaired = cr.fetchone()
        if already_repaired:
            _logger.info("xmlid %s.%s is already in place, nothing to do", GHOST_MODULE, GHOST_NAME)
        elif twin_exists:
            _logger.warning(
                "hr_contract was installed but ACL %s no longer identifies a group without xmlid:"
                " the orphan group, if there is one, is left unrepaired",
                ANCHOR_NAME,
            )
        else:
            _logger.info("hr_contract was not installed, nothing to do")

    # Any other group left without an xmlid is billed as a personalization too: log it so the next
    # module merged by Odoo does not go unnoticed.
    cr.execute(
        SQL(
            """
            SELECT g.id, g.name
              FROM res_groups g
             WHERE NOT EXISTS (SELECT 1
                                 FROM ir_model_data d
                                WHERE d.model = 'res.groups'
                                  AND d.res_id = g.id)
          ORDER BY g.id
            """
        )
    )
    remaining = cr.fetchall()
    if remaining:
        _logger.warning("Groups left without xmlid by the upgrade: %s", remaining)
