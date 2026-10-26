import logging

_logger = logging.getLogger(__name__)

# Casos de l10n_ar_edi_ux/20.0.1.0.0/post-migration.py, que pasa la leyenda del PDF
# de l10n_ar_invoice_pdf_legend_ux (backport de 19) a l10n_ar_invoice_pdf_legend
# (nativo de l10n_ar_edi en 20). Los verifica l10n_ar_edi_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: ninguna company con xmlid de la base canonica tiene
# leyenda cargada. Se crean dos companies nuevas en vez de tocar base.main_company,
# que usan como ancla otros checks.
#
# _load_records con noupdate: xmlid estable bajo 'upgrade_prepare_demo' e
# idempotente.

CASES = [
    # Rama con leyenda.
    ("company_pdf_legend_cbu", "payment_on_informed_cbu", False),
    # Rama sin leyenda, con el tilde viejo en True: el backport lo dejaba sin leer.
    ("company_pdf_legend_none", False, True),
]


def migrate(env):
    Company = env["res.company"]
    if "l10n_ar_invoice_pdf_legend_ux" not in Company._fields:
        _logger.info("l10n_ar_edi_ux is not in this database - nothing to seed")
        return

    country = env["res.country"].search([("code", "=", "AR")], limit=1)
    records = []
    for name, legend, withholding_legend in CASES:
        records.append({
            "xml_id": "upgrade_prepare_demo.%s" % name,
            "values": {
                "name": "Leyenda declarativa %s" % name,
                "country_id": country.id,
                "currency_id": env.ref("base.main_company").currency_id.id,
                "l10n_ar_invoice_pdf_legend_ux": legend,
                "l10n_ar_show_withholding_legend": withholding_legend,
            },
            "noupdate": True,
        })
    Company._load_records(records)
