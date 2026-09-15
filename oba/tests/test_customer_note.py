"""Tests for the ``add_customer_note`` helper.

They create and drop their own Postgres database. Odoo does not need to be running, only
importable.

    python3 oba/tests/test_customer_note.py

``ODOO_PATH`` and ``OBA_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("OBA_TEST_DB", "oba_customer_note_test")

sys.path.insert(0, ODOO_PATH)

import odoo.upgrade  # noqa: E402

if REPO not in odoo.upgrade.__path__:
    odoo.upgrade.__path__.append(REPO)

import psycopg2  # noqa: E402

from odoo.upgrade.oba.customer_note import TABLE  # noqa: E402


def _call_from(version_dir, body):
    """Call the helper from a script placed at ``<module>/<version>/post-migration.py``.

    Calling it straight from here would measure the test's path, not a script's.
    """
    tmp = tempfile.mkdtemp()
    script_dir = os.path.join(tmp, version_dir)
    os.makedirs(script_dir)
    script = os.path.join(script_dir, "post-migration.py")
    with open(script, "w") as fh:
        fh.write("from odoo.upgrade.oba import add_customer_note\n\n\n" + body)
    spec = importlib.util.spec_from_file_location("fake_migration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAddCustomerNote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        subprocess.run(["createdb", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = self.conn.cursor()
        self.cr.execute("DROP TABLE IF EXISTS %s" % TABLE)

    def _rows(self):
        self.cr.execute("SELECT slug, module, vals, created_at FROM %s ORDER BY slug" % TABLE)
        return self.cr.fetchall()

    def test_creates_the_table_itself(self):
        """The first caller cannot fail just because the table is not there yet."""
        _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr):\n    add_customer_note(cr, 'valoracion-stock', {'rows': []})\n",
        ).emit(self.cr)
        self.assertEqual(len(self._rows()), 1)

    def test_two_calls_leave_a_single_row(self):
        """Retrying the upgrade overwrites the stale values instead of piling up."""
        caller = _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr, rows):\n    add_customer_note(cr, 'valoracion-stock', {'rows': rows})\n",
        )
        caller.emit(self.cr, [{"orden": "PO0001"}])
        caller.emit(self.cr, [{"orden": "PO0002"}, {"orden": "PO0003"}])

        rows = self._rows()
        self.assertEqual(len(rows), 1, "the upsert by slug must overwrite, not accumulate")
        slug, module, vals, created_at = rows[0]
        self.assertEqual(slug, "valoracion-stock")
        self.assertEqual(module, "stock_account", "the module comes from the caller's path")
        self.assertEqual(vals, {"rows": [{"orden": "PO0002"}, {"orden": "PO0003"}]})
        self.assertIsNotNone(created_at, "created_at is what says which run wrote the values")

    def test_two_different_notes_coexist(self):
        _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr):\n"
            "    add_customer_note(cr, 'valoracion-stock', {'rows': [1]})\n"
            "    add_customer_note(cr, 'otra-nota', {'rows': [2]})\n",
        ).emit(self.cr)
        self.assertEqual([r[0] for r in self._rows()], ["otra-nota", "valoracion-stock"])

    def test_the_module_comes_from_the_path_not_the_slug(self):
        _call_from(
            "l10n_ar_ux/19.0.2.0.0",
            "def emit(cr):\n    add_customer_note(cr, 'valoracion-stock', {'rows': []})\n",
        ).emit(self.cr)
        self.assertEqual(self._rows()[0][1], "l10n_ar_ux")

    def test_rejects_a_malformed_slug(self):
        caller = _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr, slug):\n    add_customer_note(cr, slug, {'rows': []})\n",
        )
        for slug in ["Valoracion Stock", "valoracion_stock", "", "-valoracion", 42]:
            with self.assertRaises(ValueError) as ctx:
                caller.emit(self.cr, slug)
            self.assertIn("post-migration.py", str(ctx.exception), "the error must name the caller")

    def test_rejects_values_that_are_not_a_dict(self):
        caller = _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr, values):\n    add_customer_note(cr, 'valoracion-stock', values)\n",
        )
        with self.assertRaises(ValueError):
            caller.emit(self.cr, [1, 2, 3])

    def test_rejects_values_that_are_not_json(self):
        """The real case: rows built with tuples, and tuples do not survive jsonb."""
        caller = _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr, values):\n    add_customer_note(cr, 'valoracion-stock', values)\n",
        )
        with self.assertRaises(ValueError) as ctx:
            caller.emit(self.cr, {"rows": [object()]})
        self.assertIn("JSON-serializable", str(ctx.exception))
        self.assertIn("post-migration.py", str(ctx.exception))

    def test_rejects_a_caller_outside_the_upgrade_path(self):
        """Outside <module>/<version>/ the module we would deduce is anything at all."""
        caller = _call_from(
            "scripts/loose",
            "def emit(cr):\n    add_customer_note(cr, 'valoracion-stock', {'rows': []})\n",
        )
        with self.assertRaises(ValueError) as ctx:
            caller.emit(self.cr)
        self.assertIn("version folder", str(ctx.exception))

    def test_tuples_come_back_as_lists(self):
        """json.dumps takes them, but they return as lists: the message must not expect tuples."""
        _call_from(
            "stock_account/19.0.1.0.0",
            "def emit(cr):\n    add_customer_note(cr, 'valoracion-stock', {'rows': [('PO1', 3)]})\n",
        ).emit(self.cr)
        self.assertEqual(self._rows()[0][2], {"rows": [["PO1", 3]]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
