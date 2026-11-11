# Test declarativo de portal_timesheet/20.0.1.0.0/pre-migration.py.
#
# En 19 las dos reglas del modulo eran ir.rule de un archivo noupdate, sobre
# portal_backend.group_portal_backend. En 20 el modulo las declara como
# ir.access de security/ir.access.csv, fundidas con las ACL, sobre
# group_portal_backend_timesheet. El script les saca el noupdate para que el -u
# cargue el csv.
#
#   regla de cuentas analiticas -> ir.access ru, sin dominio, grupo de horas
#   regla de lineas de horas    -> ir.access crud, dominio de seguidor o colaborador, grupo de horas
#
# Las anclas son los propios xmlid del modulo: no hace falta siembra.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "ir.access": {
        # Regla de 19 sobre cuentas analiticas (dominio [(1,'=',1)], leer y
        # escribir, grupo portal_backend) -> lectura y escritura del grupo de
        # horas, sin dominio. Si queda otro grupo u otra operacion, el -u no
        # cargo el csv y el registro sigue como lo dejo el pase.
        ref("portal_timesheet.account_analytic_account_timesheet_portal_backend_user_access"): {
            "group_id": ref("portal_timesheet.group_portal_backend_timesheet"),
            "operation": "ru",
            "domain": None,
        },
        # Regla de 19 sobre lineas de horas (seguidor del proyecto o de la
        # tarea, crud, grupo portal_backend) -> crud del grupo de horas, para
        # seguidores y tambien para colaboradores: en 20 compartir un proyecto
        # solo crea colaboradores. Si queda en portal_backend, un usuario
        # portal-backend sin el grupo de horas carga y borra horas de los
        # proyectos que sigue.
        ref("portal_timesheet.account_analytic_line_timesheet_portal_backend_user"): {
            "group_id": ref("portal_timesheet.group_portal_backend_timesheet"),
            "operation": "crud",
            "domain": "[('project_id', '!=', False), '|', '&', ('project_id.privacy_visibility', '=', 'portal'), '|', ('project_id.message_partner_ids', 'child_of', [user.partner_id.commercial_partner_id.id]), ('task_id.message_partner_ids', 'child_of', [user.partner_id.commercial_partner_id.id]), '&', ('project_id.privacy_visibility', 'in', ['invited_users', 'portal']), ('project_id.collaborator_ids.partner_id', 'in', [user.partner_id.id])]",
        },
    },
}
