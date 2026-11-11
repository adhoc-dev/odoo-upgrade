import logging
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)

# Cases of scripts/pre_odoo/190_200/030-backup_followup_levels.py and
# modules/base/0.0.0/end-230-followup_levels.py. Checked by modules/base/tests/expected_200.py.
#
# WHY WE SEED: the demo has two levels of the main company, both manual, and no journal item
# with a level, so no company "used an automatic level in the last 180 days". We need:
#   - the main company with an automatic level used by an open invoice, a manual level that
#     sends a mail and a manual level without media;
#   - a company with an automatic level that was never used, behind a manual one;
#   - a branch of the main company without levels, with an open invoice on a level of its parent.
# The delays (-11, 11, 12) are not in the demo: they are unique per company.


def migrate(env):
    if (
        "account_followup.followup.line" not in env
        or "auto_execute" not in env["account_followup.followup.line"]._fields
    ):
        _logger.info("account_followup of 19.0 is not in this database - not seeding it")
        return
    main = env.ref("base.main_company")
    blocked = env["res.company"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.company_followup_blocked",
                "values": {"name": "Seguimiento frenado"},
                "noupdate": True,
            }
        ]
    )
    # Not again through _load_records: writing parent_id, even the same one, raises in 19.0.
    branch = env.ref("upgrade_prepare_demo.company_followup_branch", raise_if_not_found=False) or env[
        "res.company"
    ]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.company_followup_branch",
                "values": {"name": "Seguimiento sucursal", "parent_id": main.id},
                "noupdate": True,
            }
        ]
    )
    # A new branch has no journals: it posts its invoice on one of its own, with the income
    # account of its parent, whose chart it shares.
    income = (
        env["account.journal"].search([("type", "=", "sale"), ("company_id", "=", main.id)], limit=1).default_account_id
    )
    env["account.journal"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.journal_followup_branch",
                "values": {
                    "name": "Ventas sucursal seguimiento",
                    "code": "SSEG",
                    "type": "sale",
                    "company_id": branch.id,
                    "default_account_id": income.id,
                },
                "noupdate": True,
            }
        ]
    )
    template = env.ref("account_followup.demo_followup_email_template_2", raise_if_not_found=False)
    template = template.id if template else False
    levels = env["account_followup.followup.line"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.%s" % name,
                "values": dict(values, mail_template_id=template),
                "noupdate": True,
            }
            for name, values in (
                (
                    "followup_main_manual_mail",
                    {
                        "company_id": main.id,
                        "name": "Aviso previo (seguimiento)",
                        "delay": -11,
                        "auto_execute": False,
                        "send_email": True,
                    },
                ),
                (
                    "followup_main_automatic",
                    {
                        "company_id": main.id,
                        "name": "Reclamo automático (seguimiento)",
                        "delay": 11,
                        "auto_execute": True,
                        "send_email": True,
                    },
                ),
                (
                    "followup_main_no_media",
                    {
                        "company_id": main.id,
                        "name": "Compuerta (seguimiento)",
                        "delay": 12,
                        "auto_execute": False,
                        "send_email": False,
                    },
                ),
                (
                    "followup_blocked_manual_mail",
                    {
                        "company_id": blocked.id,
                        "name": "Aviso previo (frenado)",
                        "delay": -11,
                        "auto_execute": False,
                        "send_email": True,
                    },
                ),
                (
                    "followup_blocked_automatic",
                    {
                        "company_id": blocked.id,
                        "name": "Reclamo automático (frenado)",
                        "delay": 11,
                        "auto_execute": True,
                        "send_email": True,
                    },
                ),
            )
        ]
    )
    automatic = levels[1]
    # Nor a receivable account for the partner: the one of its parent.
    partner = env.ref("base.res_partner_2")
    if not partner.with_company(branch).property_account_receivable_id:
        partner.with_company(branch).property_account_receivable_id = partner.with_company(
            main
        ).property_account_receivable_id
    _invoice(env, "upgrade_prepare_demo.followup_invoice_main", main, automatic)
    _invoice(env, "upgrade_prepare_demo.followup_invoice_branch", branch, automatic)


def _invoice(env, xmlid, company, level):
    """An open invoice of 20 days ago with its receivable line on ``level``."""
    if env.ref(xmlid, raise_if_not_found=False):
        return
    date = fields.Date.context_today(env.user) - timedelta(days=20)
    journal = env["account.journal"].search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
    move = (
        env["account.move"]
        .with_company(company)
        .create(
            {
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "partner_id": env.ref("base.res_partner_2").id,
                "invoice_date": date,
                "invoice_date_due": date,
                "invoice_payment_term_id": False,
                "invoice_line_ids": [
                    (0, 0, {"name": "Seguimiento", "quantity": 1, "price_unit": 100, "tax_ids": False})
                ],
            }
        )
    )
    move.action_post()
    if move.company_id != company:
        _logger.warning("%s ended up in company %s, not in %s", xmlid, move.company_id.name, company.name)
    move.line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable").followup_line_id = level
    env["ir.model.data"].create(
        {
            "module": "upgrade_prepare_demo",
            "name": xmlid.split(".")[1],
            "model": "account.move",
            "res_id": move.id,
            "noupdate": True,
        }
    )
