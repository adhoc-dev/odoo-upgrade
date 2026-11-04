import logging

_logger = logging.getLogger(__name__)

# Company-merge case of base/19.0.0.0/end-migration.py: company B hangs from the
# main company and consolidate_branch_accounts decides what happens with the
# accounts that share a code. Checked by base/tests/expected_190.py.
# Needs the company B and the merge mapping of 035-company_merge_base.py.
#
# The store-to-branch path (030) never reaches this: it does not move the B
# account codes to the parent key, that is done by migrate_json_company_dependent,
# which only runs on a merge. So the merge is seeded for real instead of writing
# the codes by hand.

MODULE = "upgrade_prepare_demo"
COMPANY_XMLID = "%s.company_merge_b" % MODULE
MAIN_ACCOUNT_XMLID = "%s.account_merge_main_not_reconcile" % MODULE
BRANCH_ACCOUNT_XMLID = "%s.account_merge_branch_reconcile" % MODULE

# Same code, name, type and currency; only reconcile differs. The code has a
# header (2.1) and a body, so the renumbered one must stay under 2.1.
CODE = "2.1.9.99.001"
NAME = "Upgrade Merge Reconcile Case"


def migrate(env):
    if "account.account" not in env:
        _logger.info("account is not in this database - nothing to seed")
        return

    company = env.ref(COMPANY_XMLID, raise_if_not_found=False)
    if not company:
        _logger.info("Company B of the merge is not seeded - nothing to seed")
        return
    main_company = env.ref("base.main_company")

    # `code` is company dependent: it is stored under the active company, so each
    # account is loaded with its own company for the merge to find it under B.
    env["account.account"].with_company(main_company)._load_records([{
        "xml_id": MAIN_ACCOUNT_XMLID,
        "values": {
            "name": NAME,
            "code": CODE,
            "account_type": "liability_current",
            "reconcile": False,
            "company_ids": [(6, 0, [main_company.id])],
        },
        "noupdate": True,
    }])
    env["account.account"].with_company(company)._load_records([{
        "xml_id": BRANCH_ACCOUNT_XMLID,
        "values": {
            "name": NAME,
            "code": CODE,
            "account_type": "liability_current",
            "reconcile": True,
            "company_ids": [(6, 0, [company.id])],
        },
        "noupdate": True,
    }])

    _logger.info(
        "Seeded the company-merge accounts case: company %s (ID: %s)", company.name, company.id
    )
