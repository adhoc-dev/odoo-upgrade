import logging

_logger = logging.getLogger(__name__)

# Caso de la migracion COMPANY MERGE de base/19.0.0.0: dos companies A y B en
# 18, y en 19 B pasa a ser branch de A. end-migration.py mueve a la parent
# (MOVE_TO_PARENT) el company_id de lo operativo, incluidos los puntos de
# control y los equipos de calidad. Los verifica base/tests/expected_190.py.
# Usa la company B y el mapeo de 035-company_merge_base.py.

NAME = "Sucursal Fusion Declarativa"
COMPANY_XMLID = "upgrade_prepare_demo.company_merge_b"
WAREHOUSE_XMLID = "upgrade_prepare_demo.warehouse_company_merge"
TEAM_XMLID = "upgrade_prepare_demo.quality_team_company_merge"
POINT_XMLID = "upgrade_prepare_demo.quality_point_company_merge"
SPREADSHEET_TEMPLATE_XMLID = "upgrade_prepare_demo.quality_spreadsheet_template_company_merge"
CHECK_SPREADSHEET_XMLID = "upgrade_prepare_demo.quality_check_spreadsheet_company_merge"


def migrate(env):
    if "quality.point" not in env or "stock.warehouse" not in env:
        _logger.info("quality is not in this database - not seeding the company-merge case")
        return

    company = env.ref(COMPANY_XMLID, raise_if_not_found=False)
    if not company:
        _logger.info("Company B of the merge is not seeded - nothing to seed")
        return

    # 1. Un almacen de B: crear la company no crea uno, y el punto de control
    #    necesita un tipo de operacion de la misma company (check_company).
    env["stock.warehouse"].with_company(company)._load_records([{
        "xml_id": WAREHOUSE_XMLID,
        "values": {"name": NAME, "code": "UPCMB", "company_id": company.id},
        "noupdate": True,
    }])
    warehouse = env.ref(WAREHOUSE_XMLID)

    # 2. Lo de calidad de B: un equipo y un punto de control sobre la recepcion
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

    # 2.1 Las planillas de B, que solo trae quality_control: la plantilla del
    #     punto y la planilla de un control. Si quedan en la branch, el punto
    #     y el control movidos a la parent apuntan a planillas de otra company.
    if "quality.spreadsheet.template" in env:
        env["quality.spreadsheet.template"].with_company(company)._load_records([{
            "xml_id": SPREADSHEET_TEMPLATE_XMLID,
            "values": {"name": "Upgrade Company Merge Template", "company_id": company.id},
            "noupdate": True,
        }])
    if "quality.check.spreadsheet" in env:
        env["quality.check.spreadsheet"].with_company(company)._load_records([{
            "xml_id": CHECK_SPREADSHEET_XMLID,
            "values": {"name": "Upgrade Company Merge Check Spreadsheet", "company_id": company.id},
            "noupdate": True,
        }])

    _logger.info("Seeded the quality records of company %s (ID: %s)", company.name, company.id)
