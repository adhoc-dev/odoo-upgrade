import logging

_logger = logging.getLogger(__name__)

# Casos del ensanche de sale_order_line.route_company_id (18) a
# route_company_ids (19). En 18 la linea tiene UNA ruta (route_id) y el modulo
# cachea la compania de esa ruta en un m2o; en 19 la linea puede tener varias
# rutas (route_id -> route_ids, odoo/odoo@b7a9196366eb) y el cache se ensancha
# a m2m. El pre-migration del modulo mueve el dato de la columna vieja a la
# tabla de relacion.
#
# Tres ramas, sembradas desde la entrada (la ruta), no desde el cache:
#   ruta CON compania -> la compania tiene que quedar en el campo nuevo
#   ruta SIN compania -> el campo nuevo queda vacio (no se inventa nada)
#   sin ruta          -> preservacion: vacio antes y despues
#
# Los verifica route_line_test/tests/expected_190.py, que declara solo el
# estado esperado DESPUES del -u: nada valida esta data antes de que la base
# viaje a ODU (ADR 0007 de actua-20). Si la siembra fallara, lo dice el check
# post -u como ref ausente.
#
# _load_records registra los xmlids estables en ir.model.data bajo el modulo
# virtual 'upgrade_prepare_demo' y es idempotente: re-correr no duplica.

PREFIX = "upgrade_prepare_demo.%s"


def migrate(env):
    if "sale.order.line" not in env or "route_company_id" not in env["sale.order.line"]._fields:
        _logger.info("route_line_test no esta en esta base — no se siembra nada")
        return

    company = env.ref("base.main_company")

    # Una ruta con compania y otra sin: es la entrada que distingue las dos
    # primeras ramas. company_id lleva default, asi que la ruta compartida
    # necesita el False explicito.
    env["stock.route"]._load_records([
        {
            "xml_id": PREFIX % "rlt_route_con_compania",
            "values": {"name": "RLT ruta con compania", "sale_selectable": True,
                       "company_id": company.id},
            "noupdate": True,
        },
        {
            "xml_id": PREFIX % "rlt_route_sin_compania",
            "values": {"name": "RLT ruta compartida", "sale_selectable": True,
                       "company_id": False},
            "noupdate": True,
        },
    ])

    # Partner y producto propios: la base canonica va sin la demo de Odoo
    # (ADR 0005), asi que no hay de donde tomarlos prestados.
    env["res.partner"]._load_records([{
        "xml_id": PREFIX % "rlt_partner",
        "values": {"name": "RLT cliente de prueba"},
        "noupdate": True,
    }])
    env["product.product"]._load_records([{
        "xml_id": PREFIX % "rlt_product",
        "values": {"name": "RLT producto de prueba", "type": "consu"},
        "noupdate": True,
    }])
    env["sale.order"]._load_records([{
        "xml_id": PREFIX % "rlt_so",
        "values": {"partner_id": env.ref(PREFIX % "rlt_partner").id},
        "noupdate": True,
    }])

    order = env.ref(PREFIX % "rlt_so")
    product = env.ref(PREFIX % "rlt_product")
    cases = [
        ("sol_ruta_con_compania", env.ref(PREFIX % "rlt_route_con_compania").id),
        ("sol_ruta_sin_compania", env.ref(PREFIX % "rlt_route_sin_compania").id),
        ("sol_sin_ruta", False),
    ]
    records = []
    for name, route_id in cases:
        records.append({
            "xml_id": PREFIX % name,
            "values": {
                "order_id": order.id,
                "product_id": product.id,
                "name": "RLT %s" % name,
                "product_uom_qty": 1,
                "route_id": route_id,
            },
            "noupdate": True,
        })
    env["sale.order.line"]._load_records(records)
    _logger.info(
        "Seeded %s sale order lines for the route_company_id -> route_company_ids tests",
        len(records),
    )
