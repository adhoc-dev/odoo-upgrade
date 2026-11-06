import logging

_logger = logging.getLogger(__name__)

# Company dependent field on ir.actions.report, whose table is ir_act_report_xml
# and not ir_actions_report: the company merge of base/19.0.0.0/end-migration.py
# used to build the table name from the model name and failed on it.
# Needs the company B of 035-company_merge_base.py.

FIELD_NAME = "x_upgrade_prepare_company_dep"
VALUE = "value of company B"


def migrate(env):
    company_b = env.ref("upgrade_prepare_demo.company_merge_b", raise_if_not_found=False)
    if not company_b:
        _logger.info("Company B of the merge is not seeded - nothing to seed")
        return

    Fields = env["ir.model.fields"]
    field = Fields.search(
        [("model", "=", "ir.actions.report"), ("name", "=", FIELD_NAME)], limit=1
    )
    if not field:
        field = Fields.create({
            "name": FIELD_NAME,
            "model_id": env["ir.model"]._get_id("ir.actions.report"),
            "field_description": "Upgrade seed: company dependent field",
            "ttype": "char",
            "state": "manual",
            "company_dependent": True,
        })
        env.registry.clear_cache()

    report = env["ir.actions.report"].search([], order="id", limit=1)
    if not report:
        return
    report.with_company(company_b).write({FIELD_NAME: VALUE})
    _logger.info(
        "Seeded %s.%s for company %s on report %s",
        "ir.actions.report", field.name, company_b.name, report.id,
    )
