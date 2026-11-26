# stock_analytic 19 -> 20 (tasks 76564 and 79497).
#
# post-migration.py of 20.0.1.0.0 writes nothing on the customer's records: it reads the
# backup of the pre-odoo and fills the customer note data (oba_upgrade_customer_note), a
# table with no model and no xmlid, which this lane cannot read. What it emits is covered,
# case by case, by modules/stock_analytic/tests/test_draft_scraps_note.py.
NO_CHECK = (
    "El script no modifica registros del cliente: solo deja el dato del customer note en "
    "oba_upgrade_customer_note, una tabla sin modelo ni xmlid que este carril no lee. Lo que "
    "emite lo cubre modules/stock_analytic/tests/test_draft_scraps_note.py."
)
