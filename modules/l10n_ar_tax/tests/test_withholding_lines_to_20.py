"""The 19 withholding lines of l10n_ar_tax to account.payment.withholding.line, case by case.

The tests create and drop their own Postgres database with the tables the script touches, so they
need no Odoo running, only importable. The currency cases are the R.1 to R.6 of the oba-project spec
"Payment Pro — pagos en divisa y cálculo de retenciones".

    /home/odoo/venv/bin/python modules/l10n_ar_tax/tests/test_withholding_lines_to_20.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_l10n_ar_tax_withholding_test")
SCRIPT = os.path.join(REPO, "modules", "l10n_ar_tax", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402, F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

# Odoo registers a float caster for numeric, so the amounts come back as floats.

from oba.output import TABLE as OUTPUT  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("l10n_ar_tax_post_migration_20", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

ARS, USD, EUR = 1, 2, 3
COMPANY = 1
TAX_IIBB, TAX_EARNINGS = 10, 11
ACCOUNT_ENTRY, ACCOUNT_TAX = 100, 101


class Cursor:
    """A psycopg2 cursor that also takes the ``odoo.tools.SQL`` objects of the script, as Odoo's does."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if hasattr(query, "_sql_tuple"):
            query, params = query._sql_tuple[:2]
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


class WithholdingLinesCase(unittest.TestCase):
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
        self.cr = Cursor(self.conn.cursor())
        self.cr.execute(
            "DROP TABLE IF EXISTS res_currency, res_company, account_payment, account_move_line, "
            "account_tax_repartition_line, l10n_ar_payment_withholding, account_payment_withholding_line, %s, %s"
            % (script.MAP_TABLE, OUTPUT)
        )
        self.cr.execute(
            """
            CREATE TABLE res_currency (id integer PRIMARY KEY, decimal_places integer);
            CREATE TABLE res_company (id integer PRIMARY KEY, currency_id integer);
            CREATE TABLE account_payment (
                id integer PRIMARY KEY, company_id integer, currency_id integer, move_id integer,
                accounting_rate double precision, amount numeric, amount_exact double precision,
                counterpart_currency_id integer, counterpart_rate double precision,
                counterpart_currency_amount numeric
            );
            CREATE TABLE account_move_line (
                id serial PRIMARY KEY, move_id integer, tax_line_id integer, account_id integer
            );
            CREATE TABLE account_tax_repartition_line (
                id serial PRIMARY KEY, tax_id integer, repartition_type varchar, document_type varchar,
                account_id integer, sequence integer
            );
            CREATE TABLE l10n_ar_payment_withholding (
                id serial PRIMARY KEY, payment_id integer, tax_id integer, name varchar, ref text,
                base_amount numeric, amount numeric,
                create_uid integer, create_date timestamp, write_uid integer, write_date timestamp
            );
            CREATE TABLE account_payment_withholding_line (
                id serial PRIMARY KEY, tax_id integer NOT NULL, account_id integer NOT NULL,
                company_id integer NOT NULL, payment_id integer NOT NULL, name varchar, ref text,
                placeholder_type varchar NOT NULL, previous_placeholder_type varchar,
                base_amount numeric, amount numeric,
                create_uid integer, create_date timestamp, write_uid integer, write_date timestamp
            );
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            INSERT INTO res_currency VALUES (1, 2), (2, 2), (3, 2);
            INSERT INTO res_company VALUES (1, 1);
            INSERT INTO account_tax_repartition_line (tax_id, repartition_type, document_type, account_id, sequence)
            VALUES (10, 'base', 'invoice', NULL, 1), (10, 'tax', 'invoice', 101, 2), (11, 'tax', 'invoice', 101, 2);
            """.format(output=OUTPUT)
        )
        # A line of the core 20 that is not ours must not be touched.
        self.cr.execute(
            "INSERT INTO account_payment_withholding_line (tax_id, account_id, company_id, payment_id, "
            "placeholder_type, base_amount, amount) VALUES (10, 100, 1, 999, 'not_defined', 1, 1)"
        )

    def payment(self, pid, amount, currency=ARS, accounting_rate=1.0, counterpart_currency=None,
                counterpart_rate=1.0, counterpart_amount=None, amount_exact=None):
        self.cr.execute(
            "INSERT INTO account_payment VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s)",
            (pid, currency, pid, accounting_rate, amount, amount_exact, counterpart_currency or currency,
             counterpart_rate, amount if counterpart_amount is None else counterpart_amount),
        )

    def line(self, pid, tax, base, amount, name="0001-00000001", ref=None, entry=True):
        """A 19 line, in ARS; ``entry`` adds its tax line to the payment entry."""
        self.cr.execute(
            "INSERT INTO l10n_ar_payment_withholding (payment_id, tax_id, name, ref, base_amount, amount) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (pid, tax, name, ref, base, amount),
        )
        old_id = self.cr.fetchone()[0]
        if entry:
            self.cr.execute(
                "INSERT INTO account_move_line (move_id, tax_line_id, account_id) VALUES (%s, %s, %s)",
                (pid, tax, ACCOUNT_ENTRY),
            )
        return old_id

    def migrate(self):
        script.migrate(self.cr, "19.0.1.37.0")

    def new_lines(self, pid):
        self.cr.execute(
            "SELECT tax_id, account_id, company_id, name, ref, placeholder_type, base_amount, amount "
            "FROM account_payment_withholding_line WHERE payment_id = %s ORDER BY tax_id",
            (pid,),
        )
        return self.cr.fetchall()

    def payment_amounts(self, pid):
        self.cr.execute(
            "SELECT amount, amount_exact, counterpart_currency_amount FROM account_payment WHERE id = %s", (pid,)
        )
        return self.cr.fetchone()

    def warnings(self):
        self.cr.execute("SELECT payload->>'message' FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [message for (message,) in self.cr.fetchall()]


class TestCurrencies(WithholdingLinesCase):
    def test_r1_local_payment(self):
        """R.1: everything in ARS, the line keeps its values and the 97.000 net becomes 100.000."""
        self.payment(1, 97000)
        self.line(1, TAX_IIBB, 100000, 3000, ref="100000 x 3%")
        self.migrate()
        self.assertEqual(
            self.new_lines(1),
            [(TAX_IIBB, ACCOUNT_ENTRY, COMPANY, "0001-00000001", "100000 x 3%", "given_by_name",
              100000, 3000)],
        )
        self.assertEqual(self.payment_amounts(1), (100000, None, 100000))

    def test_r2_foreign_currency_payment(self):
        """R.2: USD payment at 1.000 ARS; the ARS line goes to USD with the payment rate (USD per ARS)."""
        self.payment(2, 97, currency=USD, accounting_rate=0.001, amount_exact=97.0)
        self.line(2, TAX_IIBB, 100000, 3000)
        self.migrate()
        self.assertEqual(self.new_lines(2)[0][6:], (100.00, 3.00))
        self.assertEqual(self.payment_amounts(2), (100.00, 100.0, 100.00))

    def test_r3_buying_currency(self):
        """R.3: ARS payment of a USD debt at 1.200; the line stays in ARS and the USD counterpart grows 3."""
        self.payment(3, 116400, counterpart_currency=USD, counterpart_rate=1 / 1200, counterpart_amount=97)
        self.line(3, TAX_IIBB, 120000, 3600)
        self.migrate()
        self.assertEqual(self.new_lines(3)[0][6:], (120000, 3600))
        self.assertEqual(self.payment_amounts(3), (120000, None, 100.00))

    def test_r4_advance_in_foreign_currency(self):
        """R.4: an advance without invoices behaves as R.2: the base is the advance at the payment rate."""
        self.payment(4, 97, currency=USD, accounting_rate=0.001)
        self.line(4, TAX_IIBB, 100000, 3000)
        self.migrate()
        self.assertEqual(self.new_lines(4)[0][6:], (100.00, 3.00))
        self.assertEqual(self.payment_amounts(4)[0], 100.00)

    def test_r5_arbitrage(self):
        """R.5: USD payment of an EUR debt; the line goes to USD and the EUR counterpart grows 3."""
        # USD/ARS 1.000 and EUR/ARS 1.100: 1 USD = 1000/1100 EUR
        self.payment(5, 106.70, currency=USD, accounting_rate=0.001, counterpart_currency=EUR,
                     counterpart_rate=1000 / 1100, counterpart_amount=97)
        self.line(5, TAX_IIBB, 110000, 3300)
        self.migrate()
        self.assertEqual(self.new_lines(5)[0][6:], (110.00, 3.30))
        self.assertEqual(self.payment_amounts(5), (110.00, None, 100.00))

    def test_r6_amount_edited_by_hand(self):
        """R.6: the stored 3.010 ARS is kept as 3,01 USD, it is not recomputed from the base."""
        self.payment(6, 96.99, currency=USD, accounting_rate=0.001)
        self.line(6, TAX_IIBB, 100000, 3010)
        self.migrate()
        self.assertEqual(self.new_lines(6)[0][7], 3.01)
        self.assertEqual(self.payment_amounts(6)[0], 100.00)


class TestLines(WithholdingLinesCase):
    def test_zero_line_without_entry_takes_the_tax_account(self):
        """An earnings line in zero has no tax line in the entry: its account is the tax one."""
        self.payment(7, 1000)
        self.line(7, TAX_EARNINGS, 1000, 0, name=None, entry=False)
        self.migrate()
        self.assertEqual(
            self.new_lines(7),
            [(TAX_EARNINGS, ACCOUNT_TAX, COMPANY, None, None, "not_defined", 1000, 0)],
        )
        self.assertEqual(self.payment_amounts(7)[0], 1000)

    def test_several_lines_add_up_to_the_gross(self):
        self.payment(8, 96000)
        self.line(8, TAX_IIBB, 100000, 3000)
        self.line(8, TAX_EARNINGS, 100000, 1000, name="0002-00000001")
        self.migrate()
        self.assertEqual(len(self.new_lines(8)), 2)
        self.assertEqual(self.payment_amounts(8)[0], 100000)

    def test_map_links_old_and_new_lines(self):
        self.payment(9, 97000)
        old_id = self.line(9, TAX_IIBB, 100000, 3000)
        self.migrate()
        self.cr.execute("SELECT old_id, payment_id, gross_done FROM %s" % script.MAP_TABLE)
        self.assertEqual(self.cr.fetchall(), [(old_id, 9, True)])
        self.cr.execute(
            "SELECT n.payment_id FROM %s m JOIN account_payment_withholding_line n ON n.id = m.new_id"
            % script.MAP_TABLE
        )
        self.assertEqual(self.cr.fetchall(), [(9,)])

    def test_other_lines_are_not_touched(self):
        self.migrate()
        self.cr.execute("SELECT payment_id, amount FROM account_payment_withholding_line")
        self.assertEqual(self.cr.fetchall(), [(999, 1)])


class TestLeftOut(WithholdingLinesCase):
    def test_foreign_currency_without_rate_leaves_the_payment_out(self):
        self.payment(10, 97, currency=USD, accounting_rate=0)
        self.line(10, TAX_IIBB, 100000, 3000)
        self.migrate()
        self.assertEqual(self.new_lines(10), [])
        self.assertEqual(self.payment_amounts(10)[0], 97)
        self.assertIn("no accounting rate", self.warnings()[0])

    def test_line_without_account_leaves_the_whole_payment_out(self):
        """Half the withholdings would give a wrong net: none of the payment lines goes."""
        self.payment(11, 96000)
        self.line(11, TAX_IIBB, 100000, 3000)
        self.line(11, 12, 100000, 1000, entry=False)  # tax 12 has no repartition account
        self.migrate()
        self.assertEqual(self.new_lines(11), [])
        self.assertEqual(self.payment_amounts(11)[0], 96000)
        self.assertIn("have no account", self.warnings()[0])


class TestTaxes(WithholdingLinesCase):
    """The AR taxes after the upgrade, with the 20 columns."""

    AR, US = 1, 2

    def setUp(self):
        super().setUp()
        self.cr.execute("DROP TABLE IF EXISTS account_tax, res_country")
        self.cr.execute(
            """
            CREATE TABLE res_country (id integer PRIMARY KEY, code varchar);
            CREATE TABLE account_tax (
                id integer PRIMARY KEY, country_id integer, type_tax_use varchar, is_withholding_tax boolean,
                l10n_ar_withholding_tax_type varchar, l10n_ar_code varchar
            );
            INSERT INTO res_country VALUES (1, 'AR'), (2, 'US');
            """
        )

    def tearDown(self):
        self.cr.execute("DROP TABLE IF EXISTS account_tax, res_country")

    def tax(self, tid, type_tax_use, withholding, tax_type, code=None, country=AR):
        self.cr.execute(
            "INSERT INTO account_tax VALUES (%s, %s, %s, %s, %s, %s)",
            (tid, country, type_tax_use, withholding, tax_type, code),
        )

    def tax_type(self, tid):
        self.cr.execute("SELECT l10n_ar_withholding_tax_type FROM account_tax WHERE id = %s", (tid,))
        return self.cr.fetchone()[0]

    def test_perception_loses_the_withholding_type(self):
        self.tax(1, "sale", False, "iibb_untaxed")
        self.migrate()
        self.assertIsNone(self.tax_type(1))

    def test_withholding_keeps_its_type(self):
        self.tax(2, "purchase", True, "iibb_total")
        self.migrate()
        self.assertEqual(self.tax_type(2), "iibb_total")

    def test_tax_of_another_country_is_not_touched(self):
        self.tax(3, "sale", False, "iibb_untaxed", country=self.US)
        self.migrate()
        self.assertEqual(self.tax_type(3), "iibb_untaxed")

    def test_earnings_without_code_is_warned_and_not_filled(self):
        self.tax(4, "purchase", True, "earnings")
        self.tax(5, "purchase", True, "earnings_scale", code="")
        self.tax(6, "purchase", True, "earnings", code="78")
        self.tax(7, "sale", True, "earnings")
        self.migrate()
        self.assertEqual(len(self.warnings()), 1)
        self.assertIn("2 earnings withholding taxes have no ARCA code", self.warnings()[0])
        self.assertIn("[4, 5]", self.warnings()[0])
        self.cr.execute("SELECT count(*) FROM account_tax WHERE COALESCE(l10n_ar_code, '') = ''")
        self.assertEqual(self.cr.fetchone()[0], 3)

    def test_without_the_old_table_still_checks_the_taxes(self):
        self.cr.execute("DROP TABLE l10n_ar_payment_withholding")
        self.tax(1, "sale", False, "iibb_untaxed")
        self.migrate()
        self.assertIsNone(self.tax_type(1))


class TestRuns(WithholdingLinesCase):
    def test_second_run_changes_nothing(self):
        self.payment(1, 97000)
        self.line(1, TAX_IIBB, 100000, 3000)
        self.migrate()
        self.migrate()
        self.assertEqual(len(self.new_lines(1)), 1)
        self.assertEqual(self.payment_amounts(1)[0], 100000)

    def test_without_the_old_table_does_nothing(self):
        self.cr.execute("DROP TABLE l10n_ar_payment_withholding")
        self.migrate()
        self.cr.execute("SELECT count(*) FROM account_payment_withholding_line")
        self.assertEqual(self.cr.fetchone()[0], 1)
        self.cr.execute("SELECT to_regclass(%s)", (script.MAP_TABLE,))
        self.assertIsNone(self.cr.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
