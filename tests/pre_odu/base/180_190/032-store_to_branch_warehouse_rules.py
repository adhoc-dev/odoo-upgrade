import logging

_logger = logging.getLogger(__name__)

# Casos de migrate_warehouse_stock_to_company (base/19.0.0.0/end-migration.py)
# para lo que cuelga del almacen: stock.rule con su stock.route, y
# stock.warehouse.orderpoint. Los verifica base/tests/expected_190.py.
#
# Hace falta un almacen PROPIO con store: las reglas y los orderpoints no traen
# xmlid, y el almacen tiene que terminar en una company referenciable. Por eso
# cuelga del store sembrado en 030-store_to_branch_cases.py, que se resuelve a
# la company con xmlid company_store_to_branch. Las reglas las crea el almacen
# al nacer, como en una base real; aca solo se les registra el xmlid.

STORE_XMLID = "upgrade_prepare_demo.store_to_branch"
WAREHOUSE_XMLID = "upgrade_prepare_demo.warehouse_store_to_branch"


def _register_xmlid(env, name, record):
    xmlid = "upgrade_prepare_demo.%s" % name
    if env.ref(xmlid, raise_if_not_found=False):
        return
    env["ir.model.data"].create({
        "module": "upgrade_prepare_demo",
        "name": name,
        "model": record._name,
        "res_id": record.id,
        "noupdate": True,
    })


def _delivery_rule(warehouse):
    return warehouse.delivery_route_id.rule_ids.filtered(
        lambda r: r.location_dest_id.usage == "customer"
    )[:1]


def migrate(env):
    if "stock.warehouse" not in env or "store_id" not in env["stock.warehouse"]._fields:
        _logger.info("stock_multi_store is not in this database - nothing to seed")
        return
    store = env.ref(STORE_XMLID, raise_if_not_found=False)
    if not store:
        _logger.info("The store-to-branch store was not seeded - nothing to seed")
        return

    main_company = env.ref("base.main_company")
    env["stock.warehouse"]._load_records([{
        "xml_id": WAREHOUSE_XMLID,
        "values": {
            "name": "Upgrade Store To Branch",
            "code": "UPSTB",
            "company_id": main_company.id,
            "store_id": store.id,
        },
        "noupdate": True,
    }])
    warehouse = env.ref(WAREHOUSE_XMLID)

    # Regla del almacen con store, en la main company (en 18 hay una sola).
    rule = _delivery_rule(warehouse)
    if rule:
        _register_xmlid(env, "rule_store_to_branch", rule)
        _register_xmlid(env, "route_store_to_branch", rule.route_id)

    # Preservacion: la regla del almacen de la main company, que no migra.
    main_rule = _delivery_rule(env.ref("stock.warehouse0"))
    if main_rule:
        _register_xmlid(env, "rule_main_warehouse", main_rule)

    env["product.product"]._load_records([{
        "xml_id": "upgrade_prepare_demo.product_store_to_branch",
        "values": {"name": "Upgrade Store To Branch", "type": "consu", "is_storable": True},
        "noupdate": True,
    }])
    product = env.ref("upgrade_prepare_demo.product_store_to_branch")
    if not env.ref("upgrade_prepare_demo.orderpoint_store_to_branch", raise_if_not_found=False):
        env["stock.warehouse.orderpoint"]._load_records([{
            "xml_id": "upgrade_prepare_demo.orderpoint_store_to_branch",
            "values": {
                "product_id": product.id,
                "warehouse_id": warehouse.id,
                "location_id": warehouse.lot_stock_id.id,
                "company_id": main_company.id,
                "product_min_qty": 1,
                "product_max_qty": 2,
            },
            "noupdate": True,
        }])

    _logger.info(
        "Seeded the store-to-branch warehouse case: warehouse %s (ID: %s)",
        warehouse.name, warehouse.id,
    )
