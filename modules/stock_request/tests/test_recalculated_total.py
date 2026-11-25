"""pre-migration.py and post-recalculated_total.py of stock_request 20.0.1.0.0, case by case.

The tests create and drop their own Postgres database with the tables the scripts touch, so
they need no Odoo running, only importable. Between the two scripts they change qty_done as the
post-migration.py of OCA would.

    /home/odoo/venv/bin/python modules/stock_request/tests/test_recalculated_total.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_stock_request_recalculated_test")
FOLDER = os.path.join(REPO, "modules", "stock_request", "20.0.1.0.0")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402
from odoo.tools import SQL  # noqa: E402


def _load_script(name):
    """Load a script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(FOLDER, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pre = _load_script("pre-migration")
post = _load_script("post-recalculated_total")

KEY = "stock_request_recalculated_total"


class Cursor:
    """A psycopg2 cursor that also takes odoo.tools.SQL, as the one of Odoo."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if isinstance(query, SQL):
            query, params, _fields = query._sql_tuple
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


class RecalculatedTotalCase(unittest.TestCase):
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
            """
            DROP TABLE IF EXISTS ir_module_module, stock_request, stock_request_allocation,
                                 stock_request_qty_done_bu, oba_upgrade_customer_note;
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE stock_request (id serial PRIMARY KEY, qty_done numeric);
            CREATE TABLE stock_request_allocation (id serial PRIMARY KEY, stock_request_id integer);
            INSERT INTO ir_module_module (name, state) VALUES ('stock_request', 'to upgrade');
            """
        )

    def request(self, qty_done, allocated=True):
        self.cr.execute("INSERT INTO stock_request (qty_done) VALUES (%s) RETURNING id", (qty_done,))
        request_id = self.cr.fetchone()[0]
        if allocated:
            self.cr.execute("INSERT INTO stock_request_allocation (stock_request_id) VALUES (%s)", (request_id,))
        return request_id

    def recompute(self, request_id, qty_done):
        """What the post-migration.py of OCA does to a request."""
        self.cr.execute("UPDATE stock_request SET qty_done = %s WHERE id = %s", (qty_done, request_id))

    def copy_exists(self):
        self.cr.execute("SELECT to_regclass('stock_request_qty_done_bu') IS NOT NULL")
        return self.cr.fetchone()[0]

    def note(self):
        self.cr.execute(
            "SELECT to_regclass('oba_upgrade_customer_note') IS NOT NULL"
        )
        if not self.cr.fetchone()[0]:
            return None
        self.cr.execute("SELECT value FROM oba_upgrade_customer_note WHERE key = %s", (KEY,))
        row = self.cr.fetchone()
        return row and row[0]


class TestCount(RecalculatedTotalCase):
    def test_counts_the_requests_whose_done_quantity_changed(self):
        returned = self.request(10.0)
        pushed = self.request(5.0)
        self.request(5.0)
        pre.migrate(self.cr, "19.0.1.0.4")
        self.recompute(returned, 0.0)
        self.recompute(pushed, 0.0)
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 2)

    def test_a_request_recomputed_to_the_same_value_does_not_count(self):
        request_id = self.request(5.0)
        pre.migrate(self.cr, "19.0.1.0.4")
        self.recompute(request_id, 5.0)
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 0)

    def test_a_request_without_done_quantity_that_gets_one_counts(self):
        request_id = self.request(None)
        pre.migrate(self.cr, "19.0.1.0.4")
        self.recompute(request_id, 3.0)
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 1)

    def test_a_request_without_allocations_is_not_kept(self):
        self.request(5.0, allocated=False)
        pre.migrate(self.cr, "19.0.1.0.4")
        self.cr.execute("SELECT count(*) FROM stock_request_qty_done_bu")
        self.assertEqual(self.cr.fetchone()[0], 0)

    def test_nothing_changed_is_told_as_zero(self):
        self.request(5.0)
        pre.migrate(self.cr, "19.0.1.0.4")
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 0)

    def test_a_second_run_of_the_pair_starts_from_the_values_it_finds(self):
        request_id = self.request(10.0)
        pre.migrate(self.cr, "19.0.1.0.4")
        self.recompute(request_id, 0.0)
        post.migrate(self.cr, "19.0.1.0.4")
        pre.migrate(self.cr, "19.0.1.0.4")
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 0)


class TestNotTold(RecalculatedTotalCase):
    def test_without_the_copy_nothing_is_told(self):
        self.request(5.0)
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertIsNone(self.note())

    def test_a_copy_left_by_an_earlier_run_is_replaced(self):
        request_id = self.request(5.0)
        self.cr.execute("CREATE TABLE stock_request_qty_done_bu (id integer, qty_done numeric)")
        self.cr.execute("INSERT INTO stock_request_qty_done_bu VALUES (%s, 10)", (request_id,))
        pre.migrate(self.cr, "19.0.1.0.4")
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertEqual(self.note(), 0)

    def test_without_the_module_nothing_is_kept_or_told(self):
        self.cr.execute("UPDATE ir_module_module SET state = 'uninstalled'")
        self.request(5.0)
        pre.migrate(self.cr, "19.0.1.0.4")
        post.migrate(self.cr, "19.0.1.0.4")
        self.assertFalse(self.copy_exists())
        self.assertIsNone(self.note())


if __name__ == "__main__":
    unittest.main()
