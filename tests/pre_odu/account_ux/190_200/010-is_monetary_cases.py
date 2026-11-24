import logging

_logger = logging.getLogger(__name__)

# Casos de modules/account_ux/20.0.1.0.0/post-migration.py, que pone en no
# monetarias las cuentas de tipo expense_other. Los verifica
# account_ux/tests/expected_200.py.
#
# Hay que sembrar porque el plan argentino no trae cuentas expense_other. En 19
# is_monetary se calcula por tipo, asi que la de expense_other nace monetaria,
# como en las bases de los clientes.
COMPANY_ID = 7  # Muebleria ARG de la base canonica de 19
CASES = [
    ("account_is_monetary_other_expense", "IM.01", "expense_other"),
    # Preservacion: una cuenta monetaria que el script no tiene que tocar.
    ("account_is_monetary_current_asset", "IM.02", "asset_current"),
]


def migrate(env):
    if "is_monetary" not in env["account.account"]._fields:
        _logger.info("account_ux is not in this database - nothing to seed")
        return
    company = env["res.company"].browse(COMPANY_ID).exists()
    if not company:
        _logger.info("Company %s is not in this database - nothing to seed", COMPANY_ID)
        return
    records = [
        {
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": {
                "name": "Declarative %s" % account_type,
                "code": code,
                "account_type": account_type,
                "company_ids": [(6, 0, company.ids)],
            },
            "noupdate": True,
        }
        for name, code, account_type in CASES
    ]
    env["account.account"].with_company(company)._load_records(records)
    _logger.info("Seeded %s accounts for the is_monetary tests", len(records))
