"""The withholding mode of the payments migrated to 20, case by case.

The test creates and drops its own Postgres database with the tables the script touches, so it
needs no Odoo running, only importable. ``recompute_fields`` is the one thing it stands in for:
it needs a registry, so the test checks which payments the script asks to recompute.

    /home/odoo/venv/bin/python modules/account_payment_pro/tests/test_withholding_mode_to_20.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point it at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest
from unittest import mock

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_account_payment_pro_withhold_test")
SCRIPT = os.path.join(REPO, "modules", "account_payment_pro", "20.0.1.0.0", "end-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402, F401

import psycopg2  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("account_payment_pro_end_migration_20", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

ARS, USD, CLP = 1, 2, 3  # CLP has no decimals
COMPANY = 1


class WithholdingModeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        subprocess.run(["createdb", "-E", "UTF8", "-T", "template0", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = self.conn.cursor()
        self.cr.execute("DROP TABLE IF EXISTS res_currency, account_payment, account_payment_withholding_line")
        self.cr.execute(
            """
            CREATE TABLE res_currency (id integer PRIMARY KEY, decimal_places integer);
            CREATE TABLE account_payment (
                id integer PRIMARY KEY, currency_id integer, amount numeric, withhold varchar, state varchar
            );
            CREATE TABLE account_payment_withholding_line (
                id serial PRIMARY KEY, payment_id integer NOT NULL, amount numeric
            );
            INSERT INTO res_currency VALUES (1, 2), (2, 2), (3, 0);
            """
        )

    def payment(self, pid, amount, currency=ARS, state="draft"):
        """A payment as the data migration leaves it: gross amount and the mode still unset."""
        self.cr.execute(
            "INSERT INTO account_payment VALUES (%s, %s, %s, 'payment', %s)", (pid, currency, amount, state)
        )

    def line(self, pid, amount):
        self.cr.execute(
            "INSERT INTO account_payment_withholding_line (payment_id, amount) VALUES (%s, %s)", (pid, amount)
        )

    def migrate(self):
        """Run the script, standing in for the recompute; returns the ids it asked to recompute."""
        asked = []

        def fake_recompute(cr, model, fields, ids=None, **kwargs):
            asked.append((model, tuple(fields), tuple(sorted(ids or []))))

        with mock.patch.object(script.util, "recompute_fields", fake_recompute):
            script.migrate(self.cr, "20.0.1.0.0")
        return asked

    def mode(self, pid):
        self.cr.execute("SELECT withhold FROM account_payment WHERE id = %s", (pid,))
        return self.cr.fetchone()[0]


class TestMode(WithholdingModeCase):
    def test_a_payment_with_something_left_for_the_bank_withholds_and_pays(self):
        self.payment(1, 1000)
        self.line(1, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "withhold_pay", "1000 gross less 20 withheld leaves 980 for the bank")

    def test_a_payment_that_is_all_withholding_only_withholds(self):
        self.payment(1, 20)
        self.line(1, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "withhold", "nothing goes through the bank")

    def test_a_payment_without_lines_stays_a_plain_payment(self):
        self.payment(1, 1000)

        self.migrate()

        self.assertEqual(self.mode(1), "payment")

    def test_several_withholdings_are_added_up(self):
        self.payment(1, 50)
        self.line(1, 30)
        self.line(1, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "withhold", "30 and 20 withheld leave nothing of the 50")

    def test_the_rest_is_compared_with_the_decimals_of_the_currency(self):
        """A rest the currency cannot represent is zero: the payment only withholds."""
        self.payment(1, 20.004)
        self.line(1, 20)
        self.payment(2, 20.02)
        self.line(2, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "withhold", "0.004 is zero at two decimals")
        self.assertEqual(self.mode(2), "withhold_pay", "0.02 is not")

    def test_a_currency_without_decimals_rounds_its_own_way(self):
        self.payment(1, 20.4, currency=CLP)
        self.line(1, 20)
        self.payment(2, 21, currency=CLP)
        self.line(2, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "withhold", "0.4 is zero in a currency with no decimals")
        self.assertEqual(self.mode(2), "withhold_pay")

    def test_a_payment_without_currency_is_left_alone(self):
        self.cr.execute("INSERT INTO account_payment VALUES (1, NULL, 1000, NULL, 'draft')")
        self.line(1, 20)

        self.migrate()

        self.assertEqual(self.mode(1), "payment", "with no currency there is nothing to compare, so it is not touched")


class TestRecompute(WithholdingModeCase):
    def test_only_the_drafts_with_withholdings_are_recomputed(self):
        self.payment(1, 1000)
        self.line(1, 20)
        self.payment(2, 1000, state="paid")
        self.line(2, 20)
        self.payment(3, 1000)

        asked = self.migrate()

        self.assertEqual(
            asked,
            [("account.payment", ("amount_company_currency_signed",), (1,))],
            "the posted one reads its entry and the one without withholdings did not move",
        )

    def test_nothing_is_recomputed_without_drafts(self):
        self.payment(1, 1000, state="paid")
        self.line(1, 20)

        self.assertEqual(self.migrate(), [])


class TestWithoutTheTable(WithholdingModeCase):
    def test_a_database_without_withholding_lines_is_left_alone(self):
        """The table is of l10n_account_withholding_tax: without it there is nothing to read."""
        self.cr.execute("DROP TABLE account_payment_withholding_line")
        self.payment(1, 1000)

        asked = self.migrate()

        self.assertEqual(self.mode(1), "payment", "the mode it already had")
        self.assertEqual(asked, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
