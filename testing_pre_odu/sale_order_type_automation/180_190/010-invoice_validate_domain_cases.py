import logging

_logger = logging.getLogger(__name__)

# Casos de la inversion de sale.order.type.invoice_validate_domain (18 -> 19).
# En 18 el dominio elegia las facturas que SE VALIDAN; en 19 elige las que
# QUEDAN EN BORRADOR, asi que el migration script
# (sale_order_type_automation/19.0.0.0/post-migration.py) tiene que negarlo.
# Los verifican los tests declarativos de este repo
# (sale_order_type_automation/tests/expected_190.py), que declaran solo el
# estado esperado DESPUES del -u: nada valida esta data antes de que la base
# viaje a ODU (ADR 0007 de actua-20). Si la siembra fallara, lo dice el check
# post -u como ref ausente.
#
# La rama de preservacion "tipo con automatizacion y sin dominio" NO se siembra:
# ancla en la demo del propio modulo
# (sale_order_type_automation.sale_order_type_validate_invoice_automation).
#
# _load_records (nativo de BaseModel) registra los xmlids estables en
# ir.model.data bajo el modulo virtual 'upgrade_prepare_demo' (mismo mecanismo
# que '__export__': ningun addon lo carga, asi que _process_end nunca los
# reapea) y es idempotente: re-correr el script no duplica registros.
CASES = [
    # (nombre, dominio guardado en 18)
    ("sot_ivd_single", "[('move_type', '=', 'out_invoice')]"),
    ("sot_ivd_implicit_and", "[('move_type', '=', 'out_invoice'), ('amount_total', '>', 100)]"),
    ("sot_ivd_explicit_or", "['|', ('move_type', '=', 'out_invoice'), ('amount_total', '>', 100)]"),
    ("sot_ivd_already_negated", "['!', ('move_type', '=', 'out_invoice')]"),
    # allow_expressions=True: el dominio puede traer llamadas, y el script no
    # las tiene que evaluar.
    ("sot_ivd_dynamic", "[('invoice_date', '>=', context_today())]"),
    # Preservacion: no parsea de ninguna forma, queda intacto.
    ("sot_ivd_unparseable", "[('move_type', '=',"),
    # Preservacion: '[]' es truthy como Char pero significa "validar todo".
    ("sot_ivd_empty_list", "[]"),
]


def migrate(env):
    if (
        "sale.order.type" not in env
        or "invoice_validate_domain" not in env["sale.order.type"]._fields
    ):
        _logger.info("sale_order_type_automation no esta en esta base — no se siembra nada")
        return
    records = [
        {
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": {
                "name": "Upgrade test - %s" % name,
                "invoicing_atomation": "validate_invoice",
                "invoice_validate_domain": domain,
            },
            "noupdate": True,
        }
        for name, domain in CASES
    ]
    # install_mode como la demo del modulo: _check_invoicing_journal_required
    # exige company/journal cuando la automatizacion de factura esta activa, y
    # estos tipos son company-agnostic igual que los de demo/.
    env["sale.order.type"].with_context(install_mode=True)._load_records(records)
    _logger.info(
        "Seeded %s sale order types for the invoice_validate_domain inversion tests",
        len(records),
    )
