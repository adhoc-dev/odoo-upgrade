import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# In 18.0 hr_contract declares two groups. The upgrade renames the xmlid of the first one into
# the hr module (with noupdate) and drops the one of the second, keeping the record: the group
# survives without an xmlid and is then reported as a database personalization.
TWIN_MODULE, TWIN_NAME = "hr", "group_hr_contract_employee_manager"
GHOST_MODULE, GHOST_NAME = "hr", "group_hr_contract_manager"


def migrate(cr, version):
    _logger.info("Running 'hr_contract_orphan_group' script for version %s", version)

    # Both groups come from the same module install transaction (same create_date) and are
    # consecutive, so the twin that kept its xmlid identifies the one that lost it.
    cr.execute(
        SQL(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                       create_date, write_date, create_uid, write_uid)
                 SELECT %(ghost_module)s, %(ghost_name)s, 'res.groups', ghost.id, true,
                        now(), now(), 1, 1
                   FROM res_groups ghost
                   JOIN ir_model_data twin_data
                     ON twin_data.model = 'res.groups'
                    AND twin_data.module = %(twin_module)s
                    AND twin_data.name = %(twin_name)s
                   JOIN res_groups twin
                     ON twin.id = twin_data.res_id
                  WHERE ghost.id = twin.id + 1
                    AND ghost.create_date = twin.create_date
                    AND NOT EXISTS (SELECT 1
                                      FROM ir_model_data d
                                     WHERE d.model = 'res.groups'
                                       AND d.res_id = ghost.id)
                    AND NOT EXISTS (SELECT 1
                                      FROM ir_model_data d
                                     WHERE d.module = %(ghost_module)s
                                       AND d.name = %(ghost_name)s)
              RETURNING res_id
            """,
            twin_module=TWIN_MODULE,
            twin_name=TWIN_NAME,
            ghost_module=GHOST_MODULE,
            ghost_name=GHOST_NAME,
        )
    )
    repaired = [res_id for (res_id,) in cr.fetchall()]
    _logger.info("Restored xmlid %s.%s for group(s) %s", GHOST_MODULE, GHOST_NAME, repaired or "none")

    # Any other group left without an xmlid is counted as a personalization too: log it so a
    # module merged by a future version does not go unnoticed.
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
