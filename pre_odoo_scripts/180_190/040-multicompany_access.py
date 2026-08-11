import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Da todas las companias activas a los usuarios internos.

    OJO: esto es para la base demo, no para clientes. Vive aca y no en
    upgrade-prepare-demo solo porque ese repo esta tomado por otro trabajo. Hoy no molesta
    porque el step que corre estos scripts todavia no esta en produccion, pero cuando se
    active le va a reescribir el acceso multicompania a los usuarios de cada cliente que
    actualice. Sacarlo de aca antes de ese momento.

    El crawler de Odoo (`base/tests/test_mock_crawl`) abre cada menu con un usuario demo antes
    y despues del upgrade y falla si alguno dejo de andar. En 19
    `mrp.routing.workcenter._compute_time_cycle` pasa a leer `capacity_ids` del workcenter, que
    en la demo es de una compania que el usuario no tiene permitida, y Fabricacion >
    Configuracion > Operaciones muere con AccessError (build 101516). Dandoles todas las
    companias se va la clase entera de fallas multicompania del crawler, no solo la de mrp: ya
    habia tres menus fallando antes del upgrade.

    `res_users.share` es columna real (compute con store=True) y viene en false para los
    internos, asi que alcanza con SQL y no hace falta levantar el ORM.
    """
    cr.execute(
        """
        INSERT INTO res_company_users_rel (cid, user_id)
             SELECT c.id, u.id
               FROM res_users u
         CROSS JOIN res_company c
              WHERE u.share = false
                AND c.active
                AND NOT EXISTS (
                        SELECT 1
                          FROM res_company_users_rel r
                         WHERE r.user_id = u.id
                           AND r.cid = c.id
                    )
        """
    )
    _logger.info("Gave %s missing company access row(s) to internal users", cr.rowcount)
