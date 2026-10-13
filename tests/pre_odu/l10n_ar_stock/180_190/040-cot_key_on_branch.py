import logging

_logger = logging.getLogger(__name__)

# Caso de la clave COT de ARBA cuando una compañía pasa a ser sucursal (18 -> 19).
# base/19.0.0.0/end-migration.py cuelga la sucursal de la compañía padre y le mueve los
# remitos, pero la clave COT queda en la sucursal;
# modules/l10n_ar_stock/19.0.0.0/end-migration.py se la copia a la padre si no tiene. Lo
# verifica modules/l10n_ar_stock/tests/expected_190.py.
#
# Usa la sucursal que siembra base/180_190/030-store_to_branch_cases.py y que la migración
# cuelga de base.main_company. Por eso este archivo va con el prefijo 040: las siembras
# corren por nombre de archivo, y tiene que ir después de la 030.
BRANCH_XMLID = "upgrade_prepare_demo.company_store_to_branch"
BRANCH_KEY = "COT-SUCURSAL"


def migrate(env):
    if "arba_cot" not in env["res.company"]._fields:
        _logger.info("l10n_ar_stock no esta en esta base — no se siembra nada")
        return
    branch = env.ref(BRANCH_XMLID, raise_if_not_found=False)
    if not branch:
        _logger.info("No esta la sucursal de base/030-store_to_branch_cases — no se siembra nada")
        return
    # La clave solo en la compañía que va a ser sucursal; la padre sin clave, como Odecon Srl.
    branch.arba_cot = BRANCH_KEY
    env.ref("base.main_company").arba_cot = False
    _logger.info("COT key set on %s and cleared on the main company", branch.name)
