"""Tests for ``apply_module_changes``, ``load_module_changes``, ``run_auto_discovery`` and
``jump_versions``.

They create and drop their own Postgres database with the tables the helpers touch. The
discovery reads the addons path and ``util.merge_module`` touches the whole schema, so both
are replaced by fakes; ``util.rename_module`` runs for real.

    /home/odoo/venv/bin/python lib/oba/tests/test_module_changes.py

``ODOO_PATH`` and ``OBA_TEST_DB`` point them at another checkout or another database.
"""

import glob
import json
import os
import subprocess
import sys
import tempfile
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

from oba import jump_versions, module_changes  # noqa: E402

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


class TestLoadModuleChanges(unittest.TestCase):
    """No database: it only reads the file."""

    def _load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, module_changes.MODULE_CHANGES_FILE)
            with open(path, "w") as f:
                json.dump(data, f)
            return module_changes.load_module_changes(path)

    def test_pairs_come_back_as_tuples_in_the_order_apply_takes_them(self):
        merges, renames, xmlid_renames = self._load(
            {"merge_modules": [["old", "into"]], "renamed_xmlids": [["a.old", "a.new"]]}
        )
        self.assertEqual(merges, [("old", "into")])
        self.assertEqual(renames, [])
        self.assertEqual(xmlid_renames, [("a.old", "a.new")])

    def test_a_jump_without_the_file_has_no_changes_and_warns(self):
        with self.assertLogs(module_changes._logger, "WARNING"):
            changes = module_changes.load_module_changes("/nonexistent/module_changes.json")
        self.assertEqual(changes, ([], [], []))

    def test_a_typo_raises_instead_of_skipping_the_merge(self):
        with self.assertRaisesRegex(ValueError, "merge_module"):
            self._load({"merge_module": [["old", "into"]]})
        with self.assertRaisesRegex(ValueError, "pairs"):
            self._load({"merge_modules": [["old", "into", "extra"]]})

    def test_a_file_that_is_not_an_object_of_lists_raises_value_error(self):
        for data in ([["old", "into"]], {"merge_modules": None}, {"merge_modules": {"old": "into"}}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self._load(data)

    def test_the_files_of_the_repo_and_the_template_load(self):
        pre_upgrade = os.path.join(os.path.dirname(LIB), "scripts", "pre_upgrade")
        paths = sorted(glob.glob(os.path.join(pre_upgrade, "*", module_changes.MODULE_CHANGES_FILE)))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path):
                module_changes.load_module_changes(path)
        template = os.path.join(pre_upgrade, "module_changes.template.json")
        self.assertEqual(module_changes.load_module_changes(template), ([], [], []))


class TestJumpVersions(unittest.TestCase):
    def test_the_runner_variables_win(self):
        variables = {"MYSCRIPT_FROM_VERSION": "18.0", "MYSCRIPT_TO_VERSION": "19.0"}
        with mock.patch.dict(os.environ, variables):
            self.assertEqual(jump_versions("17.0.1.3"), ("18.0", "19.0"))

    def test_without_them_base_and_the_running_odoo(self):
        with mock.patch.dict(os.environ), mock.patch("odoo.release.major_version", "20.0"):
            os.environ.pop("MYSCRIPT_FROM_VERSION", None)
            os.environ.pop("MYSCRIPT_TO_VERSION", None)
            self.assertEqual(jump_versions("19.0.1.3"), ("19.0", "20.0"))


if __name__ == "__main__":
    unittest.main()
