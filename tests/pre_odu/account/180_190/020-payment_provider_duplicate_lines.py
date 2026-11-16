import logging

_logger = logging.getLogger(__name__)

MODULE = "upgrade_prepare_demo"
PROVIDER = "payment_provider_two_lines"
# (xmlid name, journal code, electronic method, date of its payment)
LINES = [
    ("payment_method_line_old", "UPPM1", True, "2023-08-31"),
    ("payment_method_line_recent", "UPPM2", True, "2026-11-12"),
    ("payment_method_line_manual", "UPPM2", False, None),
]


def _xmlid(env, name, record):
    if not env.ref("%s.%s" % (MODULE, name), raise_if_not_found=False):
        env["ir.model.data"].create({
            "module": MODULE,
            "name": name,
            "model": record._name,
            "res_id": record.id,
            "noupdate": True,
        })


def migrate(env):
    """Seed a payment provider with lines in two journals, for
    scripts/pre_upgrade/180_190/account_payment_provider_single_method_line.py.

    The seed base may have no provider module installed, so the provider and its
    payment method use the code "none", which 19 does not count as electronic: the
    script only matches the code of the provider with the one of the method.
    18 does not let the ORM create two lines of the same provider and method in one
    company, so the lines are inserted with SQL. The third line has the manual method
    and the same provider: the script must leave it as it is.
    """
    if "payment.provider" not in env or env.ref("%s.%s" % (MODULE, PROVIDER), raise_if_not_found=False):
        return
    method = env["account.payment.method"].search([("code", "=", "none"), ("payment_type", "=", "inbound")])
    if not method:
        method = env["account.payment.method"].create({
            "name": "Upgrade case provider", "code": "none", "payment_type": "inbound",
        })
    company = env.company
    provider = env["payment.provider"].create({
        "name": "Upgrade case two lines", "code": "none", "company_id": company.id,
    })
    _xmlid(env, PROVIDER, provider)

    journals = {
        code: env["account.journal"]._load_records([{
            "xml_id": "%s.journal_%s" % (MODULE, code.lower()),
            "values": {"name": "Upgrade case %s" % code, "code": code, "type": "bank", "company_id": company.id},
            "noupdate": True,
        }])
        for code in {code for _name, code, _electronic, _date in LINES}
    }
    manual = env.ref("account.account_payment_method_manual_in")
    for name, code, electronic, date in LINES:
        env.cr.execute(
            """
            INSERT INTO account_payment_method_line
                   (name, sequence, payment_method_id, journal_id, payment_provider_id,
                    create_uid, create_date, write_uid, write_date)
            VALUES (%s, 10, %s, %s, %s, 1, now(), 1, now())
            RETURNING id
            """,
            (name, (method if electronic else manual).id, journals[code].id, provider.id),
        )
        line = env["account.payment.method.line"].browse(env.cr.fetchone()[0])
        _xmlid(env, name, line)
        if date:
            payment = env["account.payment"].create({
                "payment_type": "inbound",
                "amount": 1,
                "date": date,
                "journal_id": journals[code].id,
                "payment_method_line_id": line.id,
            })
            _xmlid(env, "payment_%s" % name, payment)
    _logger.info("Seeded provider %s with %s payment method lines", provider.name, len(LINES))
