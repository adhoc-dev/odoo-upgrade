import logging

_logger = logging.getLogger(__name__)

MODULE = "upgrade_prepare_demo"
# (xmlid name, code, type, age in days, with an entry)
CASES = [
    ("journal_purchase_old_unused", "UPJ1", "purchase", 400, False),
    ("journal_purchase_old_used", "UPJ2", "purchase", 400, True),
    ("journal_purchase_recent_unused", "UPJ3", "purchase", 0, False),
    ("journal_sale_old_unused", "UPJ4", "sale", 400, False),
]


def migrate(env):
    """Seed the favorite journals that scripts/pre_upgrade/180_190/unfavorite_unused_purchase_journals.py tells apart.

    The age of a journal is its create_date, which the ORM does not let us set, so it is
    backdated with SQL. A journal with an entry gets a draft miscellaneous entry.
    """
    if "show_on_dashboard" not in env["account.journal"]._fields:
        return

    company = env.company
    journals = env["account.journal"]._load_records(
        [
            {
                "xml_id": "%s.%s" % (MODULE, name),
                "values": {
                    "name": "Upgrade case %s" % name,
                    "code": code,
                    "type": journal_type,
                    "company_id": company.id,
                    "show_on_dashboard": True,
                },
                "noupdate": True,
            }
            for name, code, journal_type, _age, _used in CASES
        ]
    )
    for journal, (_name, _code, _type, age, used) in zip(journals, CASES):
        if age:
            env.cr.execute(
                "UPDATE account_journal SET create_date = now() - make_interval(days => %s) WHERE id = %s",
                (age, journal.id),
            )
        if used and not env["account.move"].search_count([("journal_id", "=", journal.id)]):
            env["account.move"].create({"journal_id": journal.id, "move_type": "entry"})
    _logger.info("Seeded %s journals for the unused purchase journals check", len(CASES))
