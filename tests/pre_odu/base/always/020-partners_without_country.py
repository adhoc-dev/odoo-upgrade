import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-230-fill_partner_country.py, que desde el salto a 19 le
# pone Argentina a los contactos argentinos sin pais ni provincia. Los verifican
# base/tests/expected_190.py y base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la data de prueba trae los contactos con pais. En un
# cliente aparecen porque antes de 19 el pais no hacia falta para el IVA.
#
# El pais y la provincia se vacian por SQL: asi el caso no depende de un default
# o un onchange que los complete al crear.
PARTNERS = {
    # Consumidor final sin pais ni provincia: el script le pone Argentina.
    "upgrade_prepare_demo.partner_no_country_cf": ("Upgrade: no country, CF", "l10n_ar.res_CF", None),
    # Cliente del exterior: su pais no se puede adivinar y queda vacio.
    "upgrade_prepare_demo.partner_no_country_ext": ("Upgrade: no country, foreign", "l10n_ar.res_EXT", None),
    # Sin tipo de responsabilidad: el pais no cambia la posicion fiscal y queda vacio.
    "upgrade_prepare_demo.partner_no_country_no_resp": ("Upgrade: no country, no responsibility", None, None),
    # Con provincia: Odoo ya toma el pais de la provincia y el script no lo toca.
    "upgrade_prepare_demo.partner_no_country_with_state": (
        "Upgrade: no country, with state",
        "l10n_ar.res_CF",
        "base.state_ar_c",
    ),
}


def migrate(env):
    if not env.ref("l10n_ar.res_CF", raise_if_not_found=False):
        _logger.info("l10n_ar no esta en esta base — no se siembra nada")
        return
    for xmlid, (name, responsibility, state) in PARTNERS.items():
        values = {"name": name, "is_company": True}
        if responsibility:
            values["l10n_ar_afip_responsibility_type_id"] = env.ref(responsibility).id
        env["res.partner"]._load_records([{"xml_id": xmlid, "values": values, "noupdate": True}])
        env.cr.execute(
            "UPDATE res_partner SET country_id = NULL, state_id = %s WHERE id = %s",
            (env.ref(state).id if state else None, env.ref(xmlid).id),
        )
