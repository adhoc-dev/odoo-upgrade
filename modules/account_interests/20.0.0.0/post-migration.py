import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import add_customer_note, domain_missing_fields, fix_domain_operators

_logger = logging.getLogger(__name__)

# The interest rules add `domain` to a search on account.move.line.
DOMAIN_MODEL = "account.move.line"

# What the customer note is shown: how many invalid rules and a sample of them.
SAMPLE_SIZE = 50


def migrate(cr, version):
    """Make the saved domains of the interest rules work in Odoo 20.

    `res.company.interest.domain` is a `Char` that holds a domain, and the interest cron
    evaluates it with `safe_eval` (also `academic_account_interests`). The upgrade does not
    touch it, and what 19 took with a warning, 20 rejects with a `ValueError`: the cron
    catches it, posts it on the company and skips that company, so no interests are invoiced
    for the period.

    * the operators `<>`, `==` and the ones in capitals (`IN`) are rewritten to `!=`, `=`
      and the lowercase one, which mean the same;
    * a condition on a field that no longer exists (`move_id.checked`, ...) has no
      equivalent: it is not touched, because dropping it changes which debts get interests.
      It is logged and reported to the customer note so someone fixes it by hand.
    """
    _logger.info("Running post-migration of account_interests for version %s", version)
    if not util.column_exists(cr, "res_company_interest", "domain"):
        return

    # Rules seeded by the upgrade e2e (tests/pre_odu of this repo) keep an invalid condition
    # on purpose. Only real customer data deserves the WARNING and the customer note.
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'upgrade_prepare_demo' AND model = 'res.company.interest'
        """
    )
    seeded_ids = {row[0] for row in cr.fetchall()}

    cr.execute(
        """
        SELECT id, domain
          FROM res_company_interest
         WHERE domain IS NOT NULL
           AND btrim(domain) NOT IN ('', '[]')
         ORDER BY id
        """
    )
    env = util.env(cr)
    rewritten = 0
    invalid = []
    for rule_id, raw in cr.fetchall():
        fixed = fix_domain_operators(raw)
        if fixed != raw:
            cr.execute(SQL("UPDATE res_company_interest SET domain = %s WHERE id = %s", fixed, rule_id))
            rewritten += 1
            _logger.info("res.company.interest %s: domain %r -> %r", rule_id, raw, fixed)

        missing = domain_missing_fields(env, DOMAIN_MODEL, fixed)
        if not missing:
            continue
        log = _logger.info if rule_id in seeded_ids else _logger.warning
        log(
            "res.company.interest %s: domain %r names fields %s that %s does not have in 20. "
            "The interest cron skips its company until someone fixes it by hand.%s",
            rule_id,
            fixed,
            missing,
            DOMAIN_MODEL,
            " (seeded e2e case: kept on purpose)" if rule_id in seeded_ids else "",
        )
        if rule_id not in seeded_ids:
            invalid.append((rule_id, missing))

    companies = {
        rule.id: rule.company_id.display_name
        for rule in env["res.company.interest"].browse([item[0] for item in invalid])
    }
    # Also with zero: the message can say that nothing is left to fix.
    add_customer_note(
        cr,
        {
            "interest_domains_rewritten": rewritten,
            "interest_domains_invalid_total": len(invalid),
            "interest_domains_invalid": [
                {"compania": companies.get(rule_id), "campos_inexistentes": missing}
                for rule_id, missing in invalid[:SAMPLE_SIZE]
            ],
        },
    )
