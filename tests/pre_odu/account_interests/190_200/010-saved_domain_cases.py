import logging

_logger = logging.getLogger(__name__)

# Casos de los dominios guardados de res.company.interest (19 -> 20). El campo `domain`
# (Char) se suma a la busqueda de account.move.line y el cron de intereses lo evalua con
# safe_eval; en 20 un operador que 19 aceptaba con aviso (<>, ==, en mayusculas) da
# ValueError, y el migration script (account_interests/20.0.0.0/post-migration.py) los
# reescribe. Los verifica account_interests/tests/expected_200.py, que declara solo el
# estado esperado DESPUES del -u (ADR 0007 de actua-20): si la siembra fallara, lo dice
# el check como ref ausente.
#
# Se siembran todos, tambien la rama de preservacion: la demo del modulo crea reglas sin
# dominio y el pipeline corre el -u con la demo apagada.
#
# _load_records registra los xmlids bajo el modulo virtual 'upgrade_prepare_demo' (ningun
# addon lo carga, asi que _process_end nunca los reapea) y es idempotente.
CASES = [
    ("rci_sd_not_equal", "[('move_id.move_type', '<>', 'out_refund')]"),
    ("rci_sd_double_equal", "[('parent_state', '==', 'posted')]"),
    ("rci_sd_uppercase", "[('move_id.name', 'NOT ILIKE', 'ND')]"),
    # _get_eval_context habilita context_today(): el script no la evalua.
    ("rci_sd_dynamic", "[('date', '<>', context_today())]"),
    # Preservacion: dominio que ya es valido en 20.
    ("rci_sd_valid", "[('move_id.move_type', '!=', 'out_refund')]"),
    # Operador viejo sobre un campo que 20 ya no tiene (account.move.checked).
    ("rci_sd_mixed", "[('move_id.checked', '<>', True)]"),
]


def migrate(env):
    if "res.company.interest" not in env or "domain" not in env["res.company.interest"]._fields:
        _logger.info("account_interests no esta en esta base — no se siembra nada")
        return
    company = env.company
    accounts = env["account.account"].search(
        [("account_type", "=", "asset_receivable"), ("company_ids", "in", company.id)]
    )
    if not accounts:
        _logger.warning("La compania %s no tiene cuentas a cobrar — no se siembra nada", company.name)
        return
    env["product.product"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.product_rci_sd_interest",
                "values": {"name": "Upgrade test - interest", "type": "service", "sale_ok": False},
                "noupdate": True,
            }
        ]
    )
    product = env.ref("upgrade_prepare_demo.product_rci_sd_interest")
    records = [
        {
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": {
                "company_id": company.id,
                "receivable_account_ids": [(6, 0, accounts.ids)],
                "interest_product_id": product.id,
                "rate": 0.08,
                "domain": domain,
                # Que el cron no las tome en la base del pipeline.
                "next_date": "2099-01-01",
            },
            "noupdate": True,
        }
        for name, domain in CASES
    ]
    env["res.company.interest"]._load_records(records)
    _logger.info("Seeded %s interest rules for the saved domain tests", len(records))
