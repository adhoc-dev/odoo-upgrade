"""Tests for ``should_run``, ``should_back_up`` and ``create_backup``.

One case per condition of the upgrade line, with and without a request context. They create
and drop their own Postgres database; Odoo does not need to be running, only importable, in
the target version (20.0 or later).

    /home/odoo/venv/bin/python lib/oba/tests/test_gates.py

``ODOO_PATH`` and ``OBA_TEST_DB`` point them at another checkout or another database.
"""

import json
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
LIB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("OBA_TEST_DB", "oba_gates_test")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

sys.path.insert(0, LIB)

import psycopg2  # noqa: E402
from odoo import release  # noqa: E402

from oba import create_backup, should_back_up, should_run  # noqa: E402
from oba.request_context import PARAMETER  # noqa: E402

TARGET = release.version_info[0]
# A major jump into the running Odoo.
FROM_VERSION = "%s.0.1.3" % (TARGET - 1)
BACKUP_TABLE = "oba_gates_test_bu"


class GatesCase(unittest.TestCase):
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
        self.cr.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            CREATE TABLE ir_cron (id serial PRIMARY KEY, active boolean);
            INSERT INTO ir_cron (active) VALUES (true), (false), (true);
            """
        )

    def install(self, *modules, state="installed"):
        for name in modules:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, %s)", (name, state))

    def write_context(self, **values):
        context = {
            "from_version": "%s.0" % (TARGET - 1),
            "to_version": "%s.0" % TARGET,
            "aim": "test",
            "is_first_in_series": True,
            "is_last_in_series": True,
            "parameters": {},
        }
        context.update(values)
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps(context))
        )

    def table_exists(self):
        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (BACKUP_TABLE,))
        return bool(self.cr.fetchone())


class TestShouldRun(GatesCase):
    def test_runs_on_a_major_jump_without_context(self):
        """runbot or a local -u: no request, and nothing filters but the version."""
        self.assertTrue(should_run(self.cr, FROM_VERSION))

    def test_not_on_a_minor_update(self):
        self.assertFalse(should_run(self.cr, "%s.0.1.3" % TARGET))
        self.assertFalse(should_run(self.cr, ""))

    def test_target_range(self):
        self.assertFalse(should_run(self.cr, FROM_VERSION, first_target=TARGET + 1))
        self.assertFalse(should_run(self.cr, FROM_VERSION, last_target=TARGET - 1))
        self.assertTrue(should_run(self.cr, FROM_VERSION, first_target=TARGET, last_target=TARGET))

    def test_every_module_installed(self):
        self.install("contacts")
        self.install("mail", state="uninstalled")
        self.assertTrue(should_run(self.cr, FROM_VERSION, modules=["contacts"]))
        self.assertFalse(should_run(self.cr, FROM_VERSION, modules=["contacts", "mail"]))
        self.assertFalse(should_run(self.cr, FROM_VERSION, modules=["account"]))

    def test_a_module_to_upgrade_counts_as_installed(self):
        """In the -u the modules are still being upgraded, unlike in the old database."""
        self.install("contacts", state="to upgrade")
        self.assertTrue(should_run(self.cr, FROM_VERSION, modules=["contacts"]))

    def test_position_runs_when_the_request_does_not_say(self):
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps({"aim": "test"}))
        )
        self.assertTrue(should_run(self.cr, FROM_VERSION, position="last"))

    def test_position(self):
        self.write_context(is_first_in_series=False, is_last_in_series=True)
        self.assertTrue(should_run(self.cr, FROM_VERSION, position="last"))
        self.assertFalse(should_run(self.cr, FROM_VERSION, position="first"))
        self.assertTrue(should_run(self.cr, FROM_VERSION))

    def test_aim(self):
        self.write_context(aim="production")
        self.assertFalse(should_run(self.cr, FROM_VERSION, aim="test"))
        self.assertTrue(should_run(self.cr, FROM_VERSION, aim="production"))

    def test_aim_does_not_filter_without_context(self):
        self.assertTrue(should_run(self.cr, FROM_VERSION, aim="test"))

    def test_parameter(self):
        self.write_context(parameters={"borrar_vistas_de_tablero": True, "deactivate_views_ids": []})
        self.assertTrue(should_run(self.cr, FROM_VERSION, parameter="borrar_vistas_de_tablero"))
        self.assertFalse(should_run(self.cr, FROM_VERSION, parameter="deactivate_views_ids"))
        self.assertFalse(should_run(self.cr, FROM_VERSION, parameter="activar_clarity"))

    def test_parameter_is_missing_without_context(self):
        self.assertFalse(should_run(self.cr, FROM_VERSION, parameter="activar_clarity"))

    def test_unknown_position_fails_loudly(self):
        """A typo would otherwise read a key that is never there and always run."""
        with self.assertRaises(ValueError):
            should_run(self.cr, "%s.0.1.3" % TARGET, position="last_one")


class TestShouldBackUp(GatesCase):
    def test_drops_a_table_left_by_an_earlier_run_even_when_it_skips(self):
        self.cr.execute("CREATE TABLE %s (id integer)" % BACKUP_TABLE)
        self.write_context(to_version="%s.0" % (TARGET - 1))
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET))
        self.assertFalse(self.table_exists())

    def test_backs_up_without_context(self):
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET))

    def test_target_comes_from_the_request(self):
        self.write_context()
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET))
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET + 1))
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET - 1, last_target=TARGET - 1))

    def test_unknown_position_fails_before_dropping(self):
        self.cr.execute("CREATE TABLE %s (id integer)" % BACKUP_TABLE)
        with self.assertRaises(ValueError):
            should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, position="last_one")
        self.assertTrue(self.table_exists())

    def test_target_of_a_saas_version(self):
        self.write_context(to_version="saas~%s.4" % (TARGET - 1))
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET - 1))
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET))

    def test_ceiling_does_not_filter_without_context(self):
        """Outside a provider run there is no target to compare: it backs up."""
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, last_target=TARGET - 1))

    def test_a_request_without_target_does_not_back_up(self):
        """A provider that does not send to_version only upgrades to 19."""
        self.write_context(to_version=None)
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET))

    def test_every_module_installed_in_the_old_database(self):
        self.install("spreadsheet_dashboard")
        self.install("l10n_ar_ux", state="to upgrade")
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, modules=["spreadsheet_dashboard"]))
        self.assertFalse(
            should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, modules=("spreadsheet_dashboard", "l10n_ar_ux"))
        )

    def test_position(self):
        self.write_context(is_last_in_series=False)
        self.assertFalse(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, position="last"))
        self.assertTrue(should_back_up(self.cr, BACKUP_TABLE, first_target=TARGET, position="first"))


class TestCreateBackup(GatesCase):
    def test_creates_the_table_with_its_primary_key(self):
        count = create_backup(self.cr, BACKUP_TABLE, "SELECT id FROM ir_cron WHERE active = %s", (True,))
        self.assertEqual(count, 2)
        self.cr.execute("SELECT id FROM %s ORDER BY id" % BACKUP_TABLE)
        self.assertEqual(self.cr.fetchall(), [(1,), (3,)])
        self.cr.execute(
            """
            SELECT a.attname
              FROM pg_index i
              JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
             WHERE i.indrelid = %s::regclass AND i.indisprimary
            """,
            (BACKUP_TABLE,),
        )
        self.assertEqual(self.cr.fetchall(), [("id",)])

    def test_composite_primary_key(self):
        create_backup(self.cr, BACKUP_TABLE, "SELECT id, active FROM ir_cron", primary_key=("id", "active"))
        self.cr.execute(
            "SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
            "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = %s::regclass AND i.indisprimary",
            (BACKUP_TABLE,),
        )
        self.assertEqual(self.cr.fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
