import logging

from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Caso de la migracion COMPANY MERGE de base/19.0.0.0: dos companies A y B en
# 18, y en 19 B pasa a ser branch de A. end-migration.py mueve a la parent
# (MOVE_TO_PARENT) el company_id de lo operativo, incluidos los puntos de
# control y los equipos de calidad. Los verifica base/tests/expected_190.py.
#
# POR QUE HAY QUE SEMBRAR: la base canonica arma el escenario store-to-branch
# (una company con stores), no hay una company B que se fusione con la main.
# Esta siembra crea B con su xmlid, le carga un almacen y lo de calidad, y
# declara el mapeo en migration_19_end_multicompany: sin ese parametro el modo
# depende de create_mapping, que detecta las companies por facturas cruzadas y
# en esta base no encuentra nada.
#
# El mapeo usa ids: ODU los conserva, asi que el id de B en la base 18 es el
# mismo cuando corre el end-migration en 19.

NAME = "Sucursal Fusion Declarativa"
COMPANY_XMLID = "upgrade_prepare_demo.company_merge_branch"
WAREHOUSE_XMLID = "upgrade_prepare_demo.warehouse_company_merge"
TEAM_XMLID = "upgrade_prepare_demo.quality_team_company_merge"
POINT_XMLID = "upgrade_prepare_demo.quality_point_company_merge"
MAPPING_PARAM = "migration_19_end_multicompany"


def migrate(env):
    if "quality.point" not in env or "stock.warehouse" not in env:
        _logger.info("quality is not in this database - not seeding the company-merge case")
        return

    main_company = env.ref("base.main_company")

    # 1. La company B, sin plan de cuentas y sin parent: asi llega una company
    #    hermana a la migracion. El end-migration la cuelga de la main.
    env["res.company"]._load_records([{
        "xml_id": COMPANY_XMLID,
        "values": {"name": NAME, "currency_id": main_company.currency_id.id},
        "noupdate": True,
    }])
    company = env.ref(COMPANY_XMLID)

    # 2. Un almacen de B: crear la company no crea uno, y el punto de control
    #    necesita un tipo de operacion de la misma company (check_company).
    env["stock.warehouse"].with_company(company)._load_records([{
        "xml_id": WAREHOUSE_XMLID,
        "values": {"name": NAME, "code": "UPCMB", "company_id": company.id},
        "noupdate": True,
    }])
    warehouse = env.ref(WAREHOUSE_XMLID)

    # 3. Lo de calidad de B: un equipo y un punto de control sobre la recepcion
    #    del almacen de B. Si el punto queda en la branch, confirmar una compra
    #    en la parent da error de companies.
    env["quality.alert.team"].with_company(company)._load_records([{
        "xml_id": TEAM_XMLID,
        "values": {"name": "Upgrade Company Merge Team", "company_id": company.id},
        "noupdate": True,
    }])
    team = env.ref(TEAM_XMLID)
    env["quality.point"].with_company(company)._load_records([{
        "xml_id": POINT_XMLID,
        "values": {
            "title": "Upgrade Company Merge Point",
            "company_id": company.id,
            "team_id": team.id,
            "picking_type_ids": [(6, 0, warehouse.in_type_id.ids)],
        },
        "noupdate": True,
    }])

    # 4. El mapeo A/B. Se suma a uno que ya exista para no pisar otro caso, y no
    #    se duplica si la siembra se re-corre.
    Param = env["ir.config_parameter"].sudo()
    mapping = safe_eval(Param.get_param(MAPPING_PARAM, "[]"))
    if not isinstance(mapping, (list, tuple)):
        mapping = [mapping]
    mapping = list(mapping)
    entry = {"a": main_company.id, "b": company.id}
    if entry not in mapping:
        mapping.append(entry)
        Param.set_param(MAPPING_PARAM, str(mapping))

    _logger.info(
        "Seeded the company-merge case: company %s (ID: %s) -> parent %s (ID: %s)",
        company.name, company.id, main_company.name, main_company.id,
    )
