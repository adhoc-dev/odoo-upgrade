import logging

_logger = logging.getLogger(__name__)

# Caso de scripts/pre_odoo/190_200/020-backup_partner_arca_activities.py y de
# l10n_ar_edi_ux/20.0.1.0.0/post-migration.py, que respaldan y reponen por código las
# actividades ARCA de los contactos cuando l10n_ar.arca.activity pasa de
# l10n_ar_reports_simple a l10n_ar. Lo verifica l10n_ar_edi_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: las actividades solo se cargan al consultar el padrón, así que
# ningún contacto de la base canónica tiene. Se crea un contacto nuevo para no tocar los
# que usan como ancla otros checks.
#
# _load_records con noupdate: xmlid estable bajo 'upgrade_prepare_demo' e idempotente.

PARTNER = "partner_arca_activities"
ACTIVITIES = ["l10n_ar_reports_simple.activity_11111", "l10n_ar_reports_simple.activity_11112"]


def migrate(env):
    Partner = env["res.partner"]
    if "actividades_padron" not in Partner._fields:
        _logger.info("l10n_ar_edi_ux is not in this database - nothing to seed")
        return
    activities = env["l10n_ar.arca.activity"]
    for xmlid in ACTIVITIES:
        activities |= env.ref(xmlid, raise_if_not_found=False) or activities.browse()
    if len(activities) != len(ACTIVITIES):
        _logger.info("ARCA activities of l10n_ar_reports_simple not found - nothing to seed")
        return

    Partner._load_records([{
        "xml_id": "upgrade_prepare_demo.%s" % PARTNER,
        "values": {
            "name": "Actividades ARCA declarativas",
            "country_id": env.ref("base.ar").id,
            "actividades_padron": [(6, 0, activities.ids)],
        },
        "noupdate": True,
    }])
