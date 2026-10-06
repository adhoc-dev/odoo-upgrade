"""The upgrade lines that only touch the new database, as end scripts, case by case.

Covers the scripts that are plain SQL (1470, 1812 and 2498). The tests create and drop their
own Postgres database with the tables the scripts touch, so they need no Odoo running, only
importable, in the target version (20.0 or later).

    /home/odoo/venv/bin/python modules/base/tests/test_new_database_upgrade_lines.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_new_database_lines_test")
SCRIPTS = os.path.join(REPO, "modules", "base", "0.0.0")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402
from odoo.tools import SQL  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402
from oba.request_context import PARAMETER  # noqa: E402

# A major jump: the scripts do nothing on a -u of base in the same version.
FROM_VERSION = "19.0.1.3"


def _load_script(filename):
    """Load a script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location(filename[:-3].replace("-", "_"), os.path.join(SCRIPTS, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orphan_activities = _load_script("end-130-check_orphan_activities.py")
partner_timezones = _load_script("end-140-fix_partner_timezones.py")
reconcile_labels = _load_script("end-150-unify_reconcile_model_labels.py")


class Cursor:
    """A psycopg2 cursor that also takes the ``SQL`` objects of Odoo, as the migration cursor."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if isinstance(query, SQL):
            query, params, _fields = query._sql_tuple
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


class NewDatabaseCase(unittest.TestCase):
    TABLES = ""

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
        self.cr.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            """.format(output=OUTPUT)
            + self.TABLES
        )

    def install(self, *modules):
        for name in modules:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, 'installed')", (name,))

    def write_context(self, **values):
        context = {"from_version": "19.0", "to_version": "20.0", "is_first_in_series": True, "is_last_in_series": True}
        context.update(values)
        self.cr.execute("INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps(context)))

    def logs(self, type=None):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [p["message"] for (p,) in self.cr.fetchall() if type is None or p["type"] == type]

    def rows(self, query, params=None):
        self.cr.execute(query, params)
        return self.cr.fetchall()


class TestOrphanActivities(NewDatabaseCase):
    TABLES = """
        CREATE TABLE mail_activity (id serial PRIMARY KEY, res_model varchar, res_id integer, active boolean DEFAULT true);
        CREATE TABLE res_partner (id serial PRIMARY KEY);
        INSERT INTO res_partner (id) VALUES (1), (2);
    """

    def test_warns_about_missing_documents_and_missing_models(self):
        self.install("mail")
        self.cr.execute(
            "INSERT INTO mail_activity (res_model, res_id) VALUES"
            " ('res.partner', 1), ('res.partner', 3), ('gone.model', 7)"
        )
        orphan_activities.migrate(self.cr, FROM_VERSION)
        [message] = self.logs("warning")
        self.assertIn("gone_model: target=1, qty=0", message)
        self.assertIn("res_partner: target=2, qty=1", message)

    def test_silent_when_every_document_exists(self):
        self.install("mail")
        self.cr.execute("INSERT INTO mail_activity (res_model, res_id) VALUES ('res.partner', 1), ('res.partner', 2)")
        orphan_activities.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.logs(), [])

    def test_skips_archived_activities(self):
        self.install("mail")
        self.cr.execute("INSERT INTO mail_activity (res_model, res_id, active) VALUES ('res.partner', 3, false)")
        orphan_activities.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.logs(), [])

    def test_nothing_without_mail(self):
        self.cr.execute("INSERT INTO mail_activity (res_model, res_id) VALUES ('res.partner', 3)")
        orphan_activities.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.logs(), [])


class TestPartnerTimezones(NewDatabaseCase):
    TABLES = """
        CREATE TABLE res_partner (id serial PRIMARY KEY, tz varchar);
        INSERT INTO res_partner (id, tz) VALUES
            (1, 'America/Cordoba'), (2, 'America/Rosario'), (3, 'America/Montevideo'), (4, NULL);
    """

    def timezones(self):
        return [tz for (tz,) in self.rows("SELECT tz FROM res_partner ORDER BY id")]

    def test_moves_the_old_timezones_only(self):
        self.install("contacts")
        partner_timezones.migrate(self.cr, FROM_VERSION)
        self.assertEqual(
            self.timezones(), ["America/Argentina/Cordoba", "America/Argentina/Cordoba", "America/Montevideo", None]
        )

    def test_nothing_before_the_last_jump(self):
        self.install("contacts")
        self.write_context(is_last_in_series=False)
        partner_timezones.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.timezones()[:2], ["America/Cordoba", "America/Rosario"])

    def test_nothing_without_contacts(self):
        partner_timezones.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.timezones()[0], "America/Cordoba")

    def test_nothing_on_a_minor_update(self):
        self.install("contacts")
        partner_timezones.migrate(self.cr, "20.0.1.3")
        self.assertEqual(self.timezones()[0], "America/Cordoba")


class TestReconcileModelLabels(NewDatabaseCase):
    TABLES = """
        CREATE TABLE account_reconcile_model (id serial PRIMARY KEY, name jsonb);
        CREATE TABLE account_reconcile_model_line (id serial PRIMARY KEY, model_id integer, label jsonb);
        CREATE TABLE account_move (id serial PRIMARY KEY, inalterable_hash varchar);
        CREATE TABLE account_move_line (id serial PRIMARY KEY, move_id integer, reconcile_model_id integer, name varchar);
        INSERT INTO account_reconcile_model (id, name) VALUES
            (1, '{"en_US": "Fees", "es_AR": "Comisiones"}'),
            (2, '{"en_US": "Taxes"}'),
            (3, '{"en_US": "Split"}');
        INSERT INTO account_reconcile_model_line (id, model_id, label) VALUES
            -- edited in Spanish: unified
            (10, 1, '{"en_US": "Old fee", "es_AR": "Comision bancaria"}'),
            -- edited in two languages: left as is
            (20, 2, '{"en_US": "Tax", "es_AR": "Impuesto", "es_UY": "Tributo"}'),
            -- two lines in the model: items cannot be told apart
            (30, 3, '{"en_US": "A", "es_AR": "A nuevo"}'),
            (31, 3, '{"en_US": "B"}');
        INSERT INTO account_move (id, inalterable_hash) VALUES (1, NULL), (2, 'hash');
        INSERT INTO account_move_line (id, move_id, reconcile_model_id, name) VALUES
            (100, 1, 1, 'Old fee'),
            (101, 2, 1, 'Old fee'),
            (102, 1, 1, 'Comision bancaria'),
            (200, 1, 2, 'Tax'),
            (300, 1, 3, 'A');
    """

    def run_script(self):
        self.install("account_accountant")
        reconcile_labels.migrate(self.cr, FROM_VERSION)

    def label(self, line_id):
        return self.rows("SELECT label FROM account_reconcile_model_line WHERE id = %s", (line_id,))[0][0]

    def item(self, item_id):
        return self.rows("SELECT name FROM account_move_line WHERE id = %s", (item_id,))[0][0]

    def test_unifies_the_label_edited_in_one_language(self):
        self.run_script()
        self.assertEqual(self.label(10)["en_US"], "Comision bancaria")
        self.assertEqual(self.label(30)["en_US"], "A nuevo")

    def test_leaves_the_label_edited_in_two_languages_and_warns(self):
        self.run_script()
        self.assertEqual(self.label(20)["en_US"], "Tax")
        self.assertTrue(any("line 20" in m for m in self.logs("warning")))

    def test_fixes_the_items_of_single_line_models_only(self):
        self.run_script()
        self.assertEqual([self.item(i) for i in (100, 101, 102)], ["Comision bancaria"] * 3)
        self.assertEqual(self.item(200), "Tax")
        self.assertEqual(self.item(300), "A")

    def test_counts_hashed_and_skipped_items(self):
        self.run_script()
        warnings, infos = self.logs("warning"), self.logs("info")
        self.assertTrue(any(m.startswith("1 of the fixed journal items") for m in warnings))
        self.assertTrue(any(m.startswith("1 journal items keep a label") for m in infos))

    def test_second_run_changes_nothing(self):
        self.run_script()
        before = self.rows("SELECT id, name FROM account_move_line ORDER BY id")
        self.cr.execute("DELETE FROM %s" % OUTPUT)
        reconcile_labels.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.rows("SELECT id, name FROM account_move_line ORDER BY id"), before)
        self.assertFalse(any("unified" in m or "fixed (" in m for m in self.logs()))

    def test_nothing_before_the_last_jump(self):
        self.write_context(is_last_in_series=False)
        self.run_script()
        self.assertEqual(self.label(10)["en_US"], "Old fee")


if __name__ == "__main__":
    unittest.main()
