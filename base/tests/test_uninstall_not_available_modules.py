"""The upgrade line "Módulos no disponibles" as a migration script, case by case.

The tests create and drop their own Postgres database with the tables the script touches.
The catalog is a dict per version and the removal is recorded instead of run, so they need
no network and no Odoo running, only importable.

    /home/odoo/venv/bin/python base/tests/test_uninstall_not_available_modules.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_not_available_modules_test")
SCRIPT = os.path.join(REPO, "base", "0.0.0", "end-uninstall_not_available_modules.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

if REPO not in odoo.upgrade.__path__:
    odoo.upgrade.__path__.append(REPO)

import psycopg2  # noqa: E402

from odoo.upgrade.oba.customer_note import TABLE as NOTES  # noqa: E402
from odoo.upgrade.oba.output import TABLE as OUTPUT  # noqa: E402
from odoo.upgrade.oba.request_context import PARAMETER  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("end_uninstall_not_available_modules", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

USABLE = {"state": "Usable", "state_id": 9, "state_category": "usable", "summary": None, "discarded": False}
DISCARDED = {"state": "Descartado", "state_id": 8, "state_category": "not_usable", "summary": None, "discarded": True}
MIGRATING = {
    "state": "Migrando",
    "state_id": 2,
    "state_category": "not_available",
    "summary": "Se migra en la próxima versión",
    "discarded": False,
}
ON_DEMAND = {
    "state": "A migrar según demanda",
    "state_id": 3,
    "state_category": "not_available",
    "summary": None,
    "discarded": False,
}

CATALOGS = {
    "19.0": {
        "sale": USABLE,
        "sale_ux": USABLE,
        "old_report": DISCARDED,
        "in_progress": MIGRATING,
        "on_demand": ON_DEMAND,
        # usable in one repo and discarded in another: the usable record is the entry
        "two_repos": dict(USABLE, discarded=True),
    },
    "18.0": {
        "sale": USABLE,
        "dropped_in_18": DISCARDED,
    },
}


class NotAvailableModulesCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        # UTF8 from template0: a template1 in SQL_ASCII cannot take the messages' accents
        subprocess.run(["createdb", "-E", "UTF8", "-T", "template0", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = self.conn.cursor()
        self.cr.execute(
            "DROP TABLE IF EXISTS ir_module_module_dependency, ir_module_module, ir_config_parameter, %s, %s"
            % (OUTPUT, NOTES)
        )
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_module_module_dependency (
                id serial PRIMARY KEY,
                module_id integer REFERENCES ir_module_module (id) ON DELETE CASCADE,
                name varchar NOT NULL
            );
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            CREATE TABLE {output} (
                id serial PRIMARY KEY,
                kind varchar NOT NULL,
                payload jsonb NOT NULL,
                create_date timestamp DEFAULT (now() at time zone 'UTC')
            )
            """.format(output=OUTPUT)
        )
        self.catalog_calls = []
        self.removed = []

    def modules(self, **states):
        for name, state in states.items():
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, %s)", (name, state))

    def depends(self, module, on):
        self.cr.execute(
            "INSERT INTO ir_module_module_dependency (module_id, name) SELECT id, %s FROM ir_module_module WHERE name = %s",
            (on, module),
        )

    def context(self, **overrides):
        """What the runner writes for the last request of a single-jump series."""
        context = {"from_version": "18.0", "is_first_in_series": True, "is_last_in_series": True}
        context.update(overrides)
        return context

    def write_context(self, **overrides):
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps(self.context(**overrides)))
        )

    def catalog(self, version):
        self.catalog_calls.append(version)
        return CATALOGS.get(version)

    def remove(self, cr, name):
        self.removed.append(name)
        cr.execute("DELETE FROM ir_module_module WHERE name = %s", (name,))

    def run_script(self, to_version="19.0", **overrides):
        script.run(self.cr, self.context(**overrides), to_version=to_version, catalog=self.catalog, remove=self.remove)

    def logs(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [payload for (payload,) in self.cr.fetchall()]

    def notes(self):
        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (NOTES,))
        if not self.cr.fetchone():
            return []
        self.cr.execute("SELECT slug, vals FROM %s ORDER BY slug" % NOTES)
        return self.cr.fetchall()


class TestClassification(NotAvailableModulesCase):
    def test_discarded_in_the_target_is_removed(self):
        self.modules(sale="installed", old_report="to upgrade")
        self.run_script()
        self.assertEqual(self.removed, ["old_report"])
        (log,) = self.logs()
        self.assertEqual(log["type"], "info")
        self.assertEqual(log["message"], "Módulos desinstalados: ['old_report']")
        self.assertEqual(log["migration_script"], "base/0.0.0/end-uninstall_not_available_modules.py")
        self.assertEqual(self.notes(), [])

    def test_migrating_is_removed_and_told_to_the_customer(self):
        self.modules(in_progress="to upgrade")
        self.run_script()
        self.assertEqual(self.removed, ["in_progress"])
        ((slug, vals),) = self.notes()
        self.assertEqual(slug, "modulos-no-disponibles")
        self.assertEqual(vals, {"migrar_modules_info": [["in_progress", "Se migra en la próxima versión"]]})

    def test_on_demand_is_left_for_the_po(self):
        """State 3 is not migrating: like the upgrade line, it goes to the warning, not to the customer."""
        self.modules(on_demand="to upgrade")
        self.run_script()
        self.assertEqual(self.removed, [])
        (log,) = self.logs()
        self.assertEqual(log["type"], "warning")
        self.assertIn("['on_demand'] \"A evaluar más adelante\"", log["message"])
        self.assertIn('"[AdV] Crear Tareas de Migración de Módulos"', log["message"])
        self.assertEqual(self.notes(), [])

    def test_unknown_to_every_catalog_is_left_for_the_po(self):
        self.modules(nobody_knows="to upgrade")
        self.run_script(is_first_in_series=False)
        self.assertEqual(self.removed, [])
        self.assertEqual(self.catalog_calls, ["19.0", "18.0"], "walks back to this request's origin, no further")
        (log,) = self.logs()
        self.assertEqual(log["type"], "warning")
        self.assertIn("['nobody_knows']", log["message"])

    def test_usable_still_to_install_is_not_analysed(self):
        """Marked by a previous script, installed by the next load: not a missing module."""
        self.modules(sale_ux="to install")
        self.run_script()
        self.assertEqual(self.removed, [])
        (log,) = self.logs()
        self.assertEqual(log["type"], "info")
        self.assertIn("pendientes de instalar por el fixdb", log["message"])
        self.assertIn("['sale_ux']", log["message"])

    def test_usable_in_one_repo_wins_over_discarded_in_another(self):
        self.modules(two_repos="to upgrade")
        self.run_script()
        self.assertEqual(self.removed, [])
        (log,) = self.logs()
        self.assertIn("pendientes de instalar", log["message"])

    def test_discarded_in_an_intermediate_version(self):
        """Discarded in 18 means no record in 19: the last request of 17→18→19 finds it in 18."""
        self.modules(dropped_in_18="to upgrade")
        self.run_script(is_first_in_series=False)
        self.assertEqual(self.removed, ["dropped_in_18"])
        self.assertEqual(self.catalog_calls, ["19.0", "18.0"])
        (log,) = self.logs()
        self.assertEqual(log["message"], "Módulos desinstalados: ['dropped_in_18']")

    def test_a_single_request_does_not_walk_back(self):
        """As the upgrade line: no version strictly between the origin and the target."""
        self.modules(dropped_in_18="to upgrade")
        self.run_script(is_first_in_series=True)
        self.assertEqual(self.removed, [])
        self.assertEqual(self.catalog_calls, ["19.0"])
        (log,) = self.logs()
        self.assertEqual(log["type"], "warning")

    def test_the_walk_stops_when_every_name_is_found(self):
        self.modules(old_report="to upgrade", dropped_in_18="to upgrade")
        self.run_script(is_first_in_series=False, from_version="17.0")
        self.assertEqual(self.removed, ["dropped_in_18", "old_report"])
        self.assertEqual(self.catalog_calls, ["19.0", "18.0"], "17.0 is not asked: nothing was pending")

    def test_installed_dependents_go_with_the_removed(self):
        self.modules(old_report="to upgrade", old_report_ux="to upgrade", old_report_more="to upgrade", sale="installed")
        self.depends("old_report_ux", on="old_report")
        self.depends("old_report_more", on="old_report_ux")
        self.depends("sale", on="base")
        self.run_script()
        self.assertEqual(self.removed, ["old_report_more", "old_report_ux", "old_report"], "deepest first")
        info = self.logs()[0]
        self.assertEqual(
            info["message"],
            "Módulos desinstalados: ['old_report']\nDependientes desinstalados: ['old_report_ux', 'old_report_more']",
        )

    def test_nothing_missing_leaves_no_trace(self):
        self.modules(sale="installed", sale_ux="installed")
        self.run_script()
        self.assertEqual(self.removed, [])
        self.assertEqual(self.logs(), [])
        self.assertEqual(self.notes(), [])

    def test_a_target_without_catalog_fails_loud(self):
        """No catalog means no decision; the -u has to say so rather than leave the modules alone in silence."""
        self.modules(old_report="to upgrade")
        with self.assertRaises(Exception) as ctx:
            self.run_script(to_version="99.0")
        self.assertIn("99.0", str(ctx.exception))
        self.assertEqual(self.removed, [])


class TestGate(NotAvailableModulesCase):
    def test_without_request_context_nothing_runs(self):
        """A runbot or local -u has no request: the modules are not touched."""
        self.modules(old_report="to upgrade")
        with mock.patch.object(script, "run") as run:
            script.migrate(self.cr, "19.0.1.3")
        run.assert_not_called()

    def test_not_the_last_request_nothing_runs(self):
        self.write_context(is_last_in_series=False)
        with mock.patch.object(script, "run") as run:
            script.migrate(self.cr, "19.0.1.3")
        run.assert_not_called()

    def test_the_last_request_runs_with_its_context(self):
        self.write_context(parameters={"a": 1})
        with mock.patch.object(script, "run") as run:
            script.migrate(self.cr, "19.0.1.3")
        run.assert_called_once()
        cr, context = run.call_args.args
        self.assertIs(cr, self.cr)
        self.assertEqual(context["parameters"], {"a": 1})
        self.assertEqual(context["from_version"], "18.0")


if __name__ == "__main__":
    unittest.main()
