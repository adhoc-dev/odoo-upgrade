# Test declarativo de la migración 18->19 de route_line_test.
#
# El módulo cachea en la línea de venta la compañía de su ruta. En 18 la línea
# tiene UNA ruta, así que el cache es un m2o (route_company_id); en 19 la línea
# puede tener varias (route_id -> route_ids, odoo/odoo@b7a9196366eb) y el cache
# se ensancha a m2m (route_company_ids). El pre-migration
# (route_line_test/19.0.1.0.0/pre-migration.py) mueve el dato de la columna
# vieja a la tabla de relación con util.convert_m2o_field_to_m2m.
#
#   18.0: route_company_id (m2o)      ->  19.0: route_company_ids (m2m)
#     ruta con compañía  -> esa compañía queda en el campo nuevo
#     ruta sin compañía  -> vacío (nunca hubo compañía que mover)
#     sin ruta           -> vacío (preservación)
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que
# recibimos se da por buena. Los registros llegan por xmlid desde la siembra
# (testing_pre_odu/route_line_test/180_190/010-route_company_cases.py).
#
# Por qué este caso importa: el update del módulo borra la columna vieja sin
# dejar rastro en el log, así que si el script no movió el dato antes, no hay
# error, no hay rollback y el dato no está. Un check en verde acá es la única
# señal de que el traslado ocurrió.

EXPECTED = {
    "sale.order.line": {
        # Rama principal: la línea tenía una ruta de la compañía principal, así
        # que el cache viejo valía esa compañía y el script tiene que dejarla en
        # el campo nuevo. Si acá viene [], la tabla de relación nació vacía y el
        # dato se perdió en silencio — el bug que este módulo existe para atrapar.
        ref("upgrade_prepare_demo.sol_ruta_con_compania"): {
            "route_company_ids": [ref("base.main_company")],
        },
        # Rama de la ruta compartida: la ruta existe pero no pertenece a ninguna
        # compañía, así que el cache viejo ya estaba vacío. Verifica que el
        # script no le invente una compañía a la línea por tener ruta.
        ref("upgrade_prepare_demo.sol_ruta_sin_compania"): {
            "route_company_ids": [],
        },
        # Rama de preservación: la línea nunca tuvo ruta ni compañía cacheada, y
        # tiene que seguir sin ninguna. Verifica que el traslado no alcance a los
        # registros que no pasan por la transformación.
        ref("upgrade_prepare_demo.sol_sin_ruta"): {
            "route_company_ids": [],
        },
    },
}
