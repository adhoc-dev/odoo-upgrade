import logging

_logger = logging.getLogger(__name__)

# Casos de los dominios guardados de sale.order.type (19 -> 20). Los dos Char
# (invoice_validate_domain, que se evalua contra account.move, y
# sale_order_filter_domain, contra sale.order) los evalua la automatizacion con
# safe_eval al confirmar un pedido; en 20 un operador que 19 aceptaba con aviso (<>, ==,
# en mayusculas) da ValueError, y el migration script
# (sale_order_type_automation/20.0.0.0/post-migration.py) los reescribe.
# Los verifican los tests declarativos de este repo
# (sale_order_type_automation/tests/expected_200.py), que declaran solo el estado
# esperado DESPUES del -u: nada valida esta data antes de que la base viaje a ODU
# (ADR 0007 de actua-20). Si la siembra fallara, lo dice el check post -u como ref
# ausente.
#
# Se siembran todos, tambien las ramas de preservacion, porque la data de los modulos no
# trae ningun tipo de pedido con estos dominios y el pipeline corre el -u con la demo
# apagada.
#
# _load_records (nativo de BaseModel) registra los xmlids estables en ir.model.data bajo
# el modulo virtual 'upgrade_prepare_demo' (mismo mecanismo que '__export__': ningun addon
# lo carga, asi que _process_end nunca los reapea) y es idempotente: re-correr el script no
# duplica registros.
CASES = [
    # (nombre, invoice_validate_domain, sale_order_filter_domain)
    ("sot_sd_not_equal", "[('move_type', '<>', 'out_invoice')]", False),
    ("sot_sd_double_equal", "[('state', '==', 'draft')]", False),
    ("sot_sd_uppercase", "[('name', 'ILIKE', 'FA')]", False),
    # allow_expressions=True: el dominio puede traer llamadas, y el script no las evalua.
    ("sot_sd_dynamic", "[('invoice_date', '<>', context_today())]", False),
    # El otro campo: se evalua contra sale.order.
    ("sot_sd_sale_order_filter", False, "[('state', '==', 'sale')]"),
    # Preservacion: dominios que ya son validos en 20.
    ("sot_sd_valid", "[('move_type', '=', 'out_invoice')]", "[('state', '=', 'sale')]"),
    # Preservacion: campo que 20 ya no tiene (sale.order.require_payment). No tiene
    # equivalente: el script no lo toca y lo reporta.
    ("sot_sd_missing_field", False, "[('require_payment', '=', True)]"),
    # Las dos cosas a la vez: operador viejo sobre un campo que ya no esta
    # (account.move.checked).
    ("sot_sd_mixed", "[('checked', '<>', True)]", False),
]


def migrate(env):
    if (
        "sale.order.type" not in env
        or "invoice_validate_domain" not in env["sale.order.type"]._fields
        or "sale_order_filter_domain" not in env["sale.order.type"]._fields
    ):
        _logger.info(
            "sale_order_type_automation no esta en esta base — no se siembra nada"
        )
        return
    records = []
    for name, invoice_domain, order_domain in CASES:
        values = {
            "name": "Upgrade test - %s" % name,
            "invoicing_atomation": "validate_invoice",
        }
        if invoice_domain:
            values["invoice_validate_domain"] = invoice_domain
        if order_domain:
            values["sale_order_filter_domain"] = order_domain
        records.append(
            {
                "xml_id": "upgrade_prepare_demo.%s" % name,
                "values": values,
                "noupdate": True,
            }
        )
    # install_mode como la demo del modulo: _check_invoicing_journal_required exige
    # company/journal cuando la automatizacion de factura esta activa, y estos tipos son
    # company-agnostic igual que los de demo/.
    env["sale.order.type"].with_context(install_mode=True)._load_records(records)
    _logger.info("Seeded %s sale order types for the saved domain tests", len(records))
