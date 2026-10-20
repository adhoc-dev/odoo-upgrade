import logging

_logger = logging.getLogger(__name__)

# Casos de l10n_ar_currency_update/20.0.1.0.0/pre-migration.py, que pasa
# currency_provider de 'afip' (lo agregaba el modulo en 19) a 'arca' (nativo de
# l10n_ar_edi en 20). Los verifica l10n_ar_currency_update/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la base canonica no trae demo de Odoo, y ninguna
# company con xmlid queda con 'afip'. Se crean dos companies nuevas en vez de
# tocar base.main_company, que usan como ancla otros checks.
#
# _load_records con noupdate: xmlid estable bajo 'upgrade_prepare_demo' e
# idempotente.

CASES = [
    # Rama 'afip' -> 'arca', con % y recargo para verificar que se conservan.
    ("company_currency_afip", "AR", "afip", 0.05, 1.5),
    # Preservacion: otro proveedor, el script no lo toca.
    ("company_currency_ecb", "UY", "ecb", 0.0, 0.0),
]


def migrate(env):
    Company = env["res.company"]
    if "rate_perc" not in Company._fields:
        _logger.info("l10n_ar_currency_update is not in this database - nothing to seed")
        return
    providers = dict(Company._fields["currency_provider"]._description_selection(env))
    if "afip" not in providers:
        _logger.info("The 'afip' currency provider is not in this database - nothing to seed")
        return

    records = []
    for name, country_code, provider, rate_perc, rate_surcharge in CASES:
        country = env["res.country"].search([("code", "=", country_code)], limit=1)
        records.append({
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": {
                "name": "Cotizacion declarativa %s" % provider,
                "country_id": country.id,
                "currency_id": env.ref("base.main_company").currency_id.id,
                "currency_provider": provider,
                "currency_interval_unit": "daily",
                "rate_perc": rate_perc,
                "rate_surcharge": rate_surcharge,
            },
            "noupdate": True,
        })
    Company._load_records(records)
