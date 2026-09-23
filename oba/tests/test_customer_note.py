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


MODULE_VERSION = "stock_account/19.0.1.0.0"
PASSTHROUGH = "def emit(cr, values):\n    add_customer_note(cr, values)\n"


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

    COLUMNS = ("key", "value", "module", "script", "created_at")

    def _rows(self):
        self.cr.execute("SELECT %s FROM %s ORDER BY key" % (", ".join(self.COLUMNS), TABLE))
        return [dict(zip(self.COLUMNS, row)) for row in self.cr.fetchall()]

    def test_creates_the_table_itself(self):
        """The first caller cannot fail just because the table is not there yet."""
        _call_from(
            MODULE_VERSION,
            "def emit(cr):\n    add_customer_note(cr, {'rows': []})\n",
        ).emit(self.cr)
        self.assertEqual(len(self._rows()), 1)

    def test_a_row_per_name_the_message_reads(self):
        """The message asks for the names it renders, so each one is looked up on its own."""
        _call_from(
            MODULE_VERSION,
            "def emit(cr):\n    add_customer_note(cr, {'total': 2, 'rows': [1, 2]})\n",
        ).emit(self.cr)
        self.assertEqual([(row["key"], row["value"]) for row in self._rows()], [("rows", [1, 2]), ("total", 2)])

    def test_two_calls_overwrite_instead_of_piling_up(self):
        """Retrying the upgrade rewrites the stale values, it does not add a second row."""
        caller = _call_from(
            MODULE_VERSION,
            "def emit(cr, rows):\n    add_customer_note(cr, {'rows': rows})\n",
        )
        caller.emit(self.cr, [{"orden": "PO0001"}])
        first_written_at = self._rows()[0]["created_at"]
        caller.emit(self.cr, [{"orden": "PO0002"}, {"orden": "PO0003"}])

        rows = self._rows()
        self.assertEqual(len(rows), 1, "the upsert by key must overwrite, not accumulate")
        row = rows[0]
        self.assertEqual(row["key"], "rows")
        self.assertEqual(row["module"], "stock_account", "the module comes from the caller's path")
        self.assertEqual(row["value"], [{"orden": "PO0002"}, {"orden": "PO0003"}])
        self.assertGreater(
            row["created_at"], first_written_at, "created_at has to move: it says which run wrote the value"
        )
        self.assertEqual(row["script"], "stock_account/19.0.1.0.0/post-migration.py")

    def test_the_last_script_to_write_a_name_wins(self):
        """Decided when the slug went: nothing arbitrates a shared name, and nothing fails."""
        _call_from(
            MODULE_VERSION,
            "def emit(cr):\n    add_customer_note(cr, {'rows': ['primero']})\n",
        ).emit(self.cr)
        _call_from(
            "account/19.0.1.0.0",
            "def emit(cr):\n    add_customer_note(cr, {'rows': ['segundo']})\n",
        ).emit(self.cr)

        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], ["segundo"])
        self.assertEqual(rows[0]["script"], "account/19.0.1.0.0/post-migration.py", "the row says who wrote it")

    def test_the_same_script_from_another_checkout_still_overwrites(self):
        """The stored path is relative, so a retry is a retry wherever the repo sits."""
        body = "def emit(cr, rows):\n    add_customer_note(cr, {'rows': rows})\n"
        _call_from(MODULE_VERSION, body).emit(self.cr, ["primero"])
        # A second _call_from writes the script under a different temporary directory.
        _call_from(MODULE_VERSION, body).emit(self.cr, ["segundo"])
        self.assertEqual(self._rows()[0]["value"], ["segundo"])

    def test_the_module_comes_from_the_path(self):
        _call_from(
            "l10n_ar_ux/19.0.2.0.0",
            "def emit(cr):\n    add_customer_note(cr, {'rows': []})\n",
        ).emit(self.cr)
        self.assertEqual(self._rows()[0]["module"], "l10n_ar_ux")

    def test_rejects_values_that_are_not_a_dict(self):
        caller = _call_from(
            MODULE_VERSION,
            PASSTHROUGH,
        )
        with self.assertRaises(ValueError):
            caller.emit(self.cr, [1, 2, 3])

    def test_rejects_a_key_that_cannot_be_a_variable_name(self):
        """These keys are what the message names, so one it cannot name renders nothing."""
        caller = _call_from(
            MODULE_VERSION,
            PASSTHROUGH,
        )
        for key in ["total filas", "2024", "escenario-b", "", "class", 7]:
            with self.assertRaises(ValueError, msg=key) as ctx:
                caller.emit(self.cr, {key: []})
            self.assertIn("post-migration.py", str(ctx.exception), "the error must name the caller")

    def test_rejects_values_that_are_not_json(self):
        """The real case: rows built with tuples, and tuples do not survive jsonb."""
        caller = _call_from(
            MODULE_VERSION,
            PASSTHROUGH,
        )
        with self.assertRaises(ValueError) as ctx:
            caller.emit(self.cr, {"rows": [object()]})
        self.assertIn("JSON-serializable", str(ctx.exception))
        self.assertIn("post-migration.py", str(ctx.exception))

    def test_rejects_a_caller_outside_the_upgrade_path(self):
        """Outside <module>/<version>/ the module we would deduce is anything at all."""
        caller = _call_from(
            "scripts/loose",
            "def emit(cr):\n    add_customer_note(cr, {'rows': []})\n",
        )
        with self.assertRaises(ValueError) as ctx:
            caller.emit(self.cr)
        self.assertIn("version folder", str(ctx.exception))

    def test_tuples_come_back_as_lists(self):
        """json.dumps takes them, but they return as lists: the message must not expect tuples."""
        _call_from(
            MODULE_VERSION,
            "def emit(cr):\n    add_customer_note(cr, {'rows': [('PO1', 3)]})\n",
        ).emit(self.cr)
        self.assertEqual(self._rows()[0]["value"], [["PO1", 3]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
