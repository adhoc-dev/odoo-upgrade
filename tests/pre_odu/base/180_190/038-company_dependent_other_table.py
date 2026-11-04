import logging

_logger = logging.getLogger(__name__)

# A company dependent field on a model whose table is not the model name with
# dots replaced by underscores (ir.actions.report lives in ir_act_report_xml).
# The company merge updates the field of that model by table: with the table
# derived from the name it fails with `relation "ir_actions_report" does not exist`.

MODEL = "ir.actions.report"
FIELD = "x_upgrade_company_dependent"
COMPANY_XMLID = "upgrade_prepare_demo.company_merge_b"


def migrate(env):
    company = env.ref(COMPANY_XMLID, raise_if_not_found=False)
    if not company:
        _logger.info("Company merge base is not seeded - nothing to seed")
        return

    model = env["ir.model"]._get(MODEL)
    if not env["ir.model.fields"].search_count(
        [("model_id", "=", model.id), ("name", "=", FIELD)]
    ):
        env["ir.model.fields"].create({
            "name": FIELD,
            "model_id": model.id,
            "ttype": "char",
            "state": "manual",
            "store": True,
            "company_dependent": True,
        })

    # The value of B is what the merge has to carry to the main company
    report = env[MODEL].search([], order="id", limit=1)
    report.with_company(company).write({FIELD: "seeded for the company merge"})
    _logger.info("Seeded %s.%s for company %s", MODEL, FIELD, company.name)
