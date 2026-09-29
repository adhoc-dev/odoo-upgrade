import logging

_logger = logging.getLogger(__name__)

# Casos del remapeo de purchase_order.force_delivered_status (18 -> 19):
#   'no' -> NULL, 'received' -> 'full', NULL -> preservacion.
# Los verifican los tests declarativos de este repo
# (purchase_stock_ux/tests/expected_190.py), que declaran solo el estado
# esperado DESPUES del -u: nada valida esta data antes de que la base viaje a
# ODU (ADR 0007 de actua-20). Si la siembra fallara, lo dice el check
# post -u como ref ausente.
#
# _load_records (nativo de BaseModel) registra los xmlids estables en
# ir.model.data bajo el modulo virtual 'upgrade_prepare_demo' (mismo mecanismo
# que '__export__': ningun addon lo carga, asi que _process_end nunca los
# reapea) y es idempotente: re-correr el script no duplica registros.
CASES = [
    ("po_force_delivered_no", "no"),
    ("po_force_delivered_received", "received"),
    ("po_force_delivered_null", False),
]


def migrate(env):
    if "purchase.order" not in env or "force_delivered_status" not in env["purchase.order"]._fields:
        _logger.info("purchase_stock_ux no esta en esta base — no se siembra nada")
        return
    partner = env["res.partner"].search([], limit=1)
    records = []
    for name, value in CASES:
        vals = {"partner_id": partner.id}
        if value:
            vals["force_delivered_status"] = value
        records.append({
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": vals,
            "noupdate": True,
        })
    env["purchase.order"]._load_records(records)
    _logger.info(
        "Seeded %s purchase orders for the force_delivered_status remap tests",
        len(records),
    )
