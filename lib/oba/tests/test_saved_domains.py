"""Tests for the saved domain helpers. Plain Python: no Odoo and no database.

    python3 lib/oba/tests/test_saved_domains.py
"""

import importlib.util
import os
import unittest

# Loaded by path: importing the package pulls modules that need Odoo.
_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saved_domains.py")
_spec = importlib.util.spec_from_file_location("saved_domains", _PATH)
saved_domains = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(saved_domains)

fix = saved_domains.fix_domain_operators
missing = saved_domains.domain_missing_fields


class FakeField:
    def __init__(self, type_="char", comodel_name=None):
        self.type = type_
        self.comodel_name = comodel_name
        self.relational = comodel_name is not None


class FakeModel:
    def __init__(self, fields):
        self._fields = fields


ENV = {
    "account.move.line": FakeModel(
        {
            "move_id": FakeField("many2one", "account.move"),
            "date": FakeField("date"),
            "name": FakeField(),
        }
    ),
    "account.move": FakeModel({"move_type": FakeField("selection")}),
}


class TestFixDomainOperators(unittest.TestCase):
    def test_spellings(self):
        self.assertEqual(fix("[('a', '<>', 1)]"), "[('a', '!=', 1)]")
        self.assertEqual(fix("[('a', '==', 1)]"), "[('a', '=', 1)]")

    def test_capitals_keep_the_value(self):
        self.assertEqual(fix("[('name', 'NOT ILIKE', 'FA')]"), "[('name', 'not ilike', 'FA')]")
        self.assertEqual(fix('[("a", "IN", [1])]'), '[("a", "in", [1])]')

    def test_dynamic_expression_is_not_evaluated(self):
        raw = "[('date', '<>', context_today() - relativedelta(days=30))]"
        self.assertEqual(fix(raw), "[('date', '!=', context_today() - relativedelta(days=30))]")

    def test_valid_domain_is_identical(self):
        raw = "['|', ('a', '=', 1), ('b.c', 'not in', [2, 3])]"
        self.assertEqual(fix(raw), raw)

    def test_unknown_operator_is_left_alone(self):
        self.assertEqual(fix("[('a', 'FOO', 1)]"), "[('a', 'FOO', 1)]")

    def test_idempotent(self):
        once = fix("[('a', '<>', 1), ('b', 'IN', [1])]")
        self.assertEqual(fix(once), once)


class TestDomainMissingFields(unittest.TestCase):
    def test_existing_paths(self):
        raw = "[('move_id.move_type', '!=', 'out_refund'), ('date.month_number', '=', 1)]"
        self.assertEqual(missing(ENV, "account.move.line", raw), [])

    def test_missing_paths_sorted(self):
        raw = "[('move_id.checked', '=', True), ('blocked', '=', False)]"
        self.assertEqual(missing(ENV, "account.move.line", raw), ["blocked", "move_id.checked"])


if __name__ == "__main__":
    unittest.main()
