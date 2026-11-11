import logging

_logger = logging.getLogger(__name__)

# Casos de scripts/pre_upgrade/190_200/saas_provider_untranslate_analytic_account_name.py,
# que antes de que el nombre de la cuenta analitica deje de ser traducible copia
# el nombre en es_419 al de en_US. Los verifica saas_provider/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la demo de analytic trae cuentas con el nombre solo
# en en_US. Lo que el script cambia es una cuenta renombrada desde es_419, y esa
# no la trae ninguna data de prueba.
#
# La cuenta sin es_419 es la rama de preservacion: el script no la toca y tiene
# que quedar con su nombre en en_US.
#
# Si es_419 no esta activo se activa: sin el idioma no se puede guardar el
# nombre en es_419 y no hay caso.

LANG = "es_419"
RENAMED_XMLID = "upgrade_prepare_demo.analytic_account_renamed_in_es_419"
ONLY_EN_XMLID = "upgrade_prepare_demo.analytic_account_only_en_us"


def migrate(env):
    if "use_databases" not in env["account.analytic.account"]._fields:
        _logger.info("saas_provider is not installed - not seeding it")
        return
    plan = env.ref("analytic.analytic_plan_projects", raise_if_not_found=False)
    if not plan:
        # Sin el plan no hay caso: lo dice el check como ref ausente
        _logger.info("analytic.analytic_plan_projects is not in this database - not seeding it")
        return
    if not env["res.lang"].search_count([("code", "=", LANG)]):
        lang = env["res.lang"]._activate_lang(LANG)
        env["base.language.install"].create({"lang_ids": [(6, 0, lang.ids)]}).lang_install()

    accounts = env["account.analytic.account"].with_context(lang="en_US")
    accounts._load_records(
        [
            {
                "xml_id": RENAMED_XMLID,
                "values": {"name": "Account old name", "plan_id": plan.id},
                "noupdate": True,
            },
            {
                "xml_id": ONLY_EN_XMLID,
                "values": {"name": "Account only in English", "plan_id": plan.id},
                "noupdate": True,
            },
        ]
    )
    env.ref(RENAMED_XMLID).update_field_translations("name", {LANG: "Cuenta nombre nuevo"})
