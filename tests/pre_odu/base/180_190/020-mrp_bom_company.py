import logging

_logger = logging.getLogger(__name__)


def migrate(env):
    """Le pone a cada BOM sin compania la de los workcenters de sus operaciones.

    El crawler de Odoo (`base/tests/test_mock_crawl`) abre cada menu con un usuario demo antes y
    despues del upgrade y falla si alguno dejo de andar. En la demo las BOM no tienen compania y
    sus operaciones apuntan a workcenters de Muebleria US. Como
    `mrp.routing.workcenter.company_id` es un related NO almacenado de `bom_id.company_id`, la
    regla multiempresa deja ver esas operaciones desde cualquier compania, pero el workcenter
    sigue protegido. En 19 `_compute_time_cycle` pasa a leer `capacity_ids` del workcenter, y
    Fabricacion > Configuracion > Operaciones muere con AccessError (build 101865).

    Alineando la compania la operacion deja de verse desde las otras companias y el compute no
    corre. Ademas saca una violacion latente de `check_company`: el `bom_id` de la operacion lo
    declara, o sea que Odoo ya esperaba que BOM y workcenter compartieran compania.

    Solo toca BOMs sin compania cuyas operaciones apuntan a workcenters de una sola compania,
    asi que no elige por nosotros en los casos ambiguos.
    """
    env.cr.execute(
        """
        UPDATE mrp_bom b
           SET company_id = wc.company_id
          FROM (
                  SELECT rw.bom_id, MIN(w.company_id) AS company_id
                    FROM mrp_routing_workcenter rw
                    JOIN mrp_workcenter w ON w.id = rw.workcenter_id
                   WHERE w.company_id IS NOT NULL
                GROUP BY rw.bom_id
                  HAVING COUNT(DISTINCT w.company_id) = 1
               ) wc
         WHERE b.id = wc.bom_id
           AND b.company_id IS NULL
        """
    )
    _logger.info("Set the company of %s company-less bom(s) from their workcenters", env.cr.rowcount)
