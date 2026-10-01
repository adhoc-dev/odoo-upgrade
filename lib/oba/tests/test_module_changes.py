"""Tests for ``apply_module_changes`` and ``run_auto_discovery``.

They create and drop their own Postgres database with the tables the helpers touch. The
discovery reads the addons path and ``util.merge_module`` touches the whole schema, so both
are replaced by fakes; ``util.rename_module`` runs for real.

    /home/odoo/venv/bin/python lib/oba/tests/test_module_changes.py

``ODOO_PATH`` and ``OBA_TEST_DB`` point them at another checkout or another database.
"""

import os
import subprocess
import sys
import unittest
from unittest import mock

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
LIB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("OBA_TEST_DB", "oba_module_changes_test")

sys.path.insert(0, ODOO_PATH)
sys.path.insert(0, LIB)

import psycopg2  # noqa: E402

from odoo.upgrade import util  # noqa: E402
from odoo.upgrade.util import modules as util_modules  # noqa: E402

from oba import module_changes  # noqa: E402

SCHEMA = """
    CREATE TABLE ir_module_module (
        id serial PRIMARY KEY,
        name varchar NOT NULL CONSTRAINT ir_module_module_name_uniq UNIQUE,
        state varchar,
        latest_version varchar
    );
    CREATE TABLE ir_module_module_dependency (module_id integer, name varchar);
    CREATE TABLE ir_model_data (module varchar, name varchar, model varchar);
    CREATE TABLE ir_ui_view (key varchar);
"""


class Cursor(psycopg2.extensions.cursor):
    """``rename_module`` reads the database name to look up its registry."""

    dbname = TEST_DB


class TestModuleChanges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        subprocess.run(["createdb", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)
        with cls.conn.cursor() as cr:
            cr.execute(SCHEMA)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = self.conn.cursor(cursor_factory=Cursor)
        self.addCleanup(self.conn.rollback)
        # No Odoo registry here: as in a pre_upgrade script, base is not loaded yet
        registry = mock.patch.object(util_modules, "_Registry", return_value=mock.Mock(_init_modules=set()))
        registry.start()
        self.addCleanup(registry.stop)

    def _modules(self, *rows):
        for name, state in rows:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, %s)", (name, state))

    def _state(self, name):
        self.cr.execute("SELECT state FROM ir_module_module WHERE name = %s", (name,))
        row = self.cr.fetchone()
        return row and row[0]

    def _discovery_registering(self, *names):
        """The discovery registers every module of the addons path that the base lacks."""

        def discover(cr):
            for name in names:
                cr.execute(
                    "INSERT INTO ir_module_module (name, state) VALUES (%s, 'uninstalled') ON CONFLICT DO NOTHING",
                    (name,),
                )

        return mock.patch.object(util_modules, "_trigger_auto_discovery", side_effect=discover)

    def test_rename_to_a_module_of_the_addons_path(self):
        self._modules(("sale_old", "installed"))
        with self._discovery_registering("sale_new"):
            module_changes.apply_module_changes(self.cr, "19.0.1.0", renames=[("sale_old", "sale_new")])
        self.assertIsNone(self._state("sale_old"))
        self.assertEqual(self._state("sale_new"), "installed")

    def test_merge_copies_the_state_only_from_a_module_in_use(self):
        self._modules(
            ("used_old", "installed"),
            ("used_into", "uninstalled"),
            # l10n_ar_tax_ratio -> l10n_ar_tax: a leftover row must not uninstall the target
            ("leftover_old", "uninstalled"),
            ("active_into", "installed"),
            ("missing_into", "to install"),
        )
        merges = [("used_old", "used_into"), ("leftover_old", "active_into"), ("not_in_db", "missing_into")]
        with self._discovery_registering(), mock.patch.object(util, "merge_module") as merge_module:
            module_changes.apply_module_changes(self.cr, "19.0.1.0", merges=merges)
        self.assertEqual(self._state("used_into"), "installed")
        self.assertEqual(self._state("active_into"), "installed")
        self.assertEqual(self._state("missing_into"), "to install")
        merged = [c.args[1:] for c in merge_module.call_args_list]
        self.assertEqual(merged, [("used_old", "used_into"), ("leftover_old", "active_into")])

    def test_discovery_skips_missing_dependencies_and_restores_the_patch(self):
        def new_module(cr, module, deps=(), **kwargs):
            raise util.UnknownModuleError(module)

        def discover(cr):
            util_modules.new_module(cr, "needs_missing", deps=("missing",))
            raise RuntimeError("discovery broke")

        with (
            mock.patch.object(util_modules, "new_module", new_module),
            mock.patch.object(util_modules, "_trigger_auto_discovery", side_effect=discover),
        ):
            with self.assertRaisesRegex(RuntimeError, "discovery broke"):
                module_changes.run_auto_discovery(self.cr)
            self.assertIs(util_modules.new_module, new_module)


if __name__ == "__main__":
    unittest.main()
