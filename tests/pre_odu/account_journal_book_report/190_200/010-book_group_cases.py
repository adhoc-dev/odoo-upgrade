import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-220-journal_book_groups_to_ledgers.py, que en el salto a
# 20 pasa los grupos del libro diario de account_journal_book_report a Ledgers. Los
# verifica base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: el modulo no trae data de prueba, asi que la base
# canonica no tiene grupos del libro diario ni diarios que los usen.
#
#   journal_book_group_none     sin grupo                  -> sigue sin Ledger
#   journal_book_group_sales    grupo propio               -> Ledger nuevo
#   journal_book_group_clash    grupo con el nombre de un  -> Ledger nuevo con
#                               Ledger que ya existe          sufijo
#
# El Ledger que ya existe excluye a los tres diarios: en 19 un Ledger reune a
# todos los diarios menos los excluidos, y asi ninguno de los sembrados entra en
# el. Como lo pasa Odoo a 20 no esta verificado: si el pase le asigna ese Ledger
# a un diario sembrado, el check lo muestra.

MODULE = "upgrade_prepare_demo"
SALES_GROUP = "Upgrade case book group"
CLASH_NAME = "Upgrade case ledger clash"
# (xmlid name, code, book group name)
JOURNALS = [
    ("journal_book_group_none", "UBG0", None),
    ("journal_book_group_sales", "UBG1", SALES_GROUP),
    ("journal_book_group_clash", "UBG2", CLASH_NAME),
]


def migrate(env):
    if "account.journal.book.group" not in env or "book_group_id" not in env["account.journal"]._fields:
        return

    groups = env["account.journal.book.group"]._load_records(
        [
            {"xml_id": "%s.book_group_sales" % MODULE, "values": {"name": SALES_GROUP}, "noupdate": True},
            {"xml_id": "%s.book_group_clash" % MODULE, "values": {"name": CLASH_NAME}, "noupdate": True},
        ]
    )
    group_by_name = {group.name: group.id for group in groups}

    company = env.company
    journals = env["account.journal"]._load_records(
        [
            {
                "xml_id": "%s.%s" % (MODULE, name),
                "values": {
                    "name": "Upgrade case %s" % name,
                    "code": code,
                    "type": "general",
                    "company_id": company.id,
                    "book_group_id": group_by_name.get(group_name, False),
                },
                "noupdate": True,
            }
            for name, code, group_name in JOURNALS
        ]
    )

    env["account.journal.group"]._load_records(
        [
            {
                "xml_id": "%s.ledger_book_group_clash" % MODULE,
                "values": {
                    "name": CLASH_NAME,
                    "company_id": company.id,
                    "excluded_journal_ids": [(6, 0, journals.ids)],
                },
                "noupdate": True,
            }
        ]
    )
    _logger.info("Seeded %s journals for the book groups to ledgers check", len(JOURNALS))
