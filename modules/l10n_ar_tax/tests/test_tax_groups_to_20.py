"""l10n_ar_tax 19 -> 20: the jurisdiction and the withholding sequence of the AR taxes go to their tax group.

The tests create and drop their own Postgres database with the tables the script touches, so they
need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/l10n_ar_tax/tests/test_tax_groups_to_20.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_l10n_ar_tax_groups_test")
SCRIPT = os.path.join(REPO, "modules", "l10n_ar_tax", "20.0.1.0.0", "pre-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402, F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("l10n_ar_tax_pre_migration_20", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

AR, US = 1, 2
CABA, BA = 50, 51
SEQ_A, SEQ_B = 70, 71


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


class TaxGroupsCase(unittest.TestCase):
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
        self.cr.execute("DROP TABLE IF EXISTS res_country, account_tax_group, account_tax, %s" % OUTPUT)
        self.cr.execute(
            """
            CREATE TABLE res_country (id integer PRIMARY KEY, code varchar);
            CREATE TABLE account_tax_group (id integer PRIMARY KEY);
            CREATE TABLE account_tax (
                id integer PRIMARY KEY, tax_group_id integer, country_id integer, type_tax_use varchar,
                is_withholding_tax boolean, l10n_ar_state_id integer, withholding_sequence_id integer
            );
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            INSERT INTO res_country VALUES (1, 'AR'), (2, 'US');
            """.format(output=OUTPUT)
        )

    def group(self, gid):
        self.cr.execute("INSERT INTO account_tax_group (id) VALUES (%s)", (gid,))

    def tax(self, tid, gid, type_tax_use="purchase", withholding=True, state=None, sequence=None, country=AR):
        self.cr.execute(
            "INSERT INTO account_tax VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (tid, gid, country, type_tax_use, withholding, state, sequence),
        )

    def migrate(self):
        script.migrate(self.cr, "19.0.1.38.0")

    def group_values(self, gid):
        self.cr.execute(
            "SELECT l10n_ar_state_id, withholding_sequence_id FROM account_tax_group WHERE id = %s", (gid,)
        )
        return self.cr.fetchone()

    def tax_values(self, tid):
        self.cr.execute("SELECT l10n_ar_state_id, withholding_sequence_id FROM account_tax WHERE id = %s", (tid,))
        return self.cr.fetchone()

    def warnings(self):
        self.cr.execute("SELECT payload->>'message' FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [message for (message,) in self.cr.fetchall()]


class TestCopy(TaxGroupsCase):
    def test_jurisdiction_group_takes_both_values(self):
        """A province group: the supplier withholding has the sequence, the customer one only the jurisdiction."""
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.tax(11, 1, type_tax_use="sale", state=CABA)
        self.migrate()
        self.assertEqual(self.group_values(1), (CABA, SEQ_A))
        self.assertEqual(self.warnings(), [])

    def test_earnings_group_takes_the_shared_sequence(self):
        self.group(2)
        self.tax(20, 2, sequence=SEQ_A)
        self.tax(21, 2, sequence=SEQ_A)
        self.tax(22, 2, type_tax_use="sale")
        self.migrate()
        self.assertEqual(self.group_values(2), (None, SEQ_A))
        self.assertEqual(self.warnings(), [])

    def test_perception_group_takes_the_jurisdiction(self):
        self.group(3)
        self.tax(30, 3, type_tax_use="sale", withholding=False, state=BA)
        self.tax(31, 3, type_tax_use="purchase", withholding=False, state=BA)
        self.migrate()
        self.assertEqual(self.group_values(3), (BA, None))

    def test_group_without_values_stays_empty(self):
        self.group(4)
        self.tax(40, 4, type_tax_use="sale", withholding=False)
        self.migrate()
        self.assertEqual(self.group_values(4), (None, None))
        self.assertEqual(self.warnings(), [])

    def test_taxes_of_another_country_are_not_read(self):
        self.group(5)
        self.tax(50, 5, state=CABA, sequence=SEQ_A)
        self.tax(51, 5, state=BA, sequence=SEQ_B, country=US)
        self.migrate()
        self.assertEqual(self.group_values(5), (CABA, SEQ_A))
        self.assertEqual(self.warnings(), [])


class TestConflicts(TaxGroupsCase):
    def test_different_jurisdictions_are_warned_and_not_chosen(self):
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.tax(11, 1, state=BA, sequence=SEQ_A)
        self.migrate()
        self.assertEqual(self.group_values(1), (None, SEQ_A))
        self.assertEqual(len(self.warnings()), 1)
        self.assertIn("1 AR tax groups have taxes with a different jurisdiction", self.warnings()[0])
        self.assertIn("1 (10:%s, 11:%s)" % (CABA, BA), self.warnings()[0])

    def test_different_supplier_sequences_are_warned_and_not_chosen(self):
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.tax(11, 1, state=CABA, sequence=SEQ_B)
        self.migrate()
        self.assertEqual(self.group_values(1), (CABA, None))
        self.assertEqual(len(self.warnings()), 1)
        self.assertIn("different withholding sequence", self.warnings()[0])
        with self.subTest("the taxes keep their values"):
            self.assertEqual(self.tax_values(10), (CABA, SEQ_A))
            self.assertEqual(self.tax_values(11), (CABA, SEQ_B))


class TestTaxesWithoutValue(TaxGroupsCase):
    def test_a_tax_without_jurisdiction_takes_the_one_of_its_group(self):
        """A perception left without jurisdiction in 19 is not a difference: it takes the group's."""
        self.group(1)
        self.tax(10, 1, type_tax_use="sale", withholding=False, state=CABA)
        self.tax(11, 1, type_tax_use="sale", withholding=False)
        self.migrate()
        self.assertEqual(self.group_values(1), (CABA, None))
        self.assertEqual(self.tax_values(11), (CABA, None))
        self.assertEqual(self.warnings(), [])

    def test_a_supplier_withholding_without_sequence_takes_the_one_of_its_group(self):
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.tax(11, 1, state=CABA)
        self.migrate()
        self.assertEqual(self.group_values(1), (CABA, SEQ_A))
        self.assertEqual(self.tax_values(11), (CABA, SEQ_A))
        self.assertEqual(self.warnings(), [])

    def test_customer_withholding_loses_its_sequence_without_warning(self):
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.tax(11, 1, type_tax_use="sale", state=CABA, sequence=SEQ_B)
        self.migrate()
        self.assertEqual(self.group_values(1), (CABA, SEQ_A))
        self.assertEqual(self.tax_values(11), (CABA, None))
        self.assertEqual(self.warnings(), [])


class TestRuns(TaxGroupsCase):
    def test_a_group_value_is_not_overwritten_and_a_second_run_changes_nothing(self):
        self.group(1)
        self.tax(10, 1, state=CABA, sequence=SEQ_A)
        self.migrate()
        self.cr.execute("UPDATE account_tax_group SET l10n_ar_state_id = %s WHERE id = 1", (BA,))
        self.migrate()
        self.assertEqual(self.group_values(1), (BA, SEQ_A))

    def test_without_groups_does_nothing(self):
        self.cr.execute("DROP TABLE account_tax_group")
        self.migrate()
        self.assertEqual(self.warnings(), [])


if __name__ == "__main__":
    unittest.main()
