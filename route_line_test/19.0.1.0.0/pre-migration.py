import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# En 19 `sale.order.line.route_id` paso a ser `route_ids` (Many2many,
# odoo/odoo@b7a9196366eb), asi que el campo que cachea la compania de la ruta
# tambien se ensancha: route_company_id (m2o) -> route_company_ids (m2m).
_MODEL = "sale.order.line"
_TABLE = "sale_order_line"
_OLD_FIELD = "route_company_id"
_NEW_FIELD = "route_company_ids"


def migrate(cr, version):
    """Convierte route_company_id (m2o) en route_company_ids (m2m).

    Tiene que correr en **pre-migration**, no en post: el update del modulo
    borra la columna `route_company_id` y su registro en `ir_model_fields`
    **sin dejar rastro en el log** (medido en una base 19), asi que cuando
    corre el post-migration el dato viejo ya no existe.

    `convert_m2o_field_to_m2m` hace las cuatro cosas: crea la tabla de relacion
    con el nombre que genera el ORM (las dos tablas en orden alfabetico ->
    `res_company_sale_order_line_rel`), la llena desde la columna vieja, borra
    esa columna y renombra el campo en `ir_model_fields`.

    Que este lleno antes del update es lo que evita el escenario malo: si la
    tabla llegara vacia al update, el recompute del campo la llenaria desde
    `route_ids` — y si el pase de core de `route_id` -> `route_ids` no corrio,
    escribiria vacio sobre un dato que ya no se puede recuperar.
    """
    _logger.info("Running pre-migration for route_line_test %s", version)

    if not util.column_exists(cr, _TABLE, _OLD_FIELD):
        _logger.info("%s.%s no existe: nada que convertir", _TABLE, _OLD_FIELD)
        return

    util.convert_m2o_field_to_m2m(cr, _MODEL, _OLD_FIELD, new_name=_NEW_FIELD)
