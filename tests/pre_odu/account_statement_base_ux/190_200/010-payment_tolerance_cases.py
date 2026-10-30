import logging

_logger = logging.getLogger(__name__)

# Casos de la tolerancia de pago de account.reconcile.model (19 -> 20):
#   automatico con tolerancia -> regla de coincidencia, manual con tolerancia -> sin tolerancia,
#   automatico sin tolerancia -> preservacion.
# Los verifica el test declarativo de account_statement_base_ux/tests/expected_200.py.
CASES = [
    ("reconcile_model_tolerance_auto", "Tolerance auto", "auto_reconcile", 50.0),
    ("reconcile_model_tolerance_manual", "Tolerance manual", "manual", 30.0),
    ("reconcile_model_no_tolerance_auto", "No tolerance auto", "auto_reconcile", 0.0),
]


def migrate(env):
    model = env.get("account.reconcile.model")
    if model is None or "payment_tolerance" not in model._fields:
        _logger.info("account_statement_base_ux no esta en esta base — no se siembra nada")
        return
    records = [
        {
            "xml_id": "upgrade_prepare_demo.%s" % xml_name,
            "values": {"name": name, "trigger": trigger, "payment_tolerance": tolerance},
            "noupdate": True,
        }
        for xml_name, name, trigger, tolerance in CASES
    ]
    model._load_records(records)
    _logger.info("Sembrados %s modelos de conciliacion con tolerancia de pago", len(records))
