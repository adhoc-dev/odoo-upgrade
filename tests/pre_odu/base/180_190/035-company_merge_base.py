import logging

_logger = logging.getLogger(__name__)

# Company B of the company merge mode of base/19.0.0.0/end-migration.py.
# Other seeds that need the merge reuse this company and this parameter.

COMPANY_XMLID = "upgrade_prepare_demo.company_merge_b"
NAME = "Compania Fusionada"


def migrate(env):
    main_company = env.ref("base.main_company")
    env["res.company"]._load_records([{
        "xml_id": COMPANY_XMLID,
        "values": {"name": NAME, "currency_id": main_company.currency_id.id},
        "noupdate": True,
    }])
    company = env.ref(COMPANY_XMLID)

    # Do not override a mapping set by hand
    params = env["ir.config_parameter"].sudo()
    if not params.get_param("migration_19_end_multicompany"):
        params.set_param(
            "migration_19_end_multicompany",
            repr({"a": main_company.id, "b": company.id}),
        )
    _logger.info("Seeded company merge: %s -> %s", company.name, main_company.name)
