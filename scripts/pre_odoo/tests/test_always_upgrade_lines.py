"""The upgrade lines that run on the old database before the pass to Odoo, case by case.

Covers 090 and 100 of ``scripts/pre_odoo/always``. The tests create and drop their own
Postgres database with the tables the scripts touch, so they need no Odoo running, only
importable (any version: the scripts are plain SQL).

    /home/odoo/venv/bin/python scripts/pre_odoo/tests/test_always_upgrade_lines.py

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
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_pre_odoo_lines_test")
SCRIPTS = os.path.join(REPO, "scripts", "pre_odoo", "always")

try:
    import odoo  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402
from oba.request_context import PARAMETER  # noqa: E402


def _load_script(filename):
    """Load a script by path: the folder is not a package and the name starts with a digit."""
    name = "s" + filename[:-3].replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


user_type = _load_script("090-single_user_type_group.py")
method_lines = _load_script("100-unique_payment_method_line_names.py")


class OldDatabaseCase(unittest.TestCase):
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
        self.cr = self.conn.cursor()
        self.cr.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            CREATE TABLE ir_model_data (
                id serial PRIMARY KEY, module varchar, name varchar, model varchar, res_id integer
            );
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            """.format(output=OUTPUT)
            + self.TABLES
        )

    def install(self, *modules):
        for name in modules:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, 'installed')", (name,))

    def write_context(self, **values):
        context = {
            "from_version": "19.0",
            "to_version": "20.0",
            "is_first_in_series": True,
            "is_last_in_series": True,
        }
        context.update(values)
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps(context))
        )

    def xmlid(self, module, name, model, res_id):
        self.cr.execute(
            "INSERT INTO ir_model_data (module, name, model, res_id) VALUES (%s, %s, %s, %s)",
            (module, name, model, res_id),
        )

    def logs(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [(p["type"], p["message"]) for (p,) in self.cr.fetchall()]

    def rows(self, query, params=None):
        self.cr.execute(query, params)
        return self.cr.fetchall()


class TestSingleUserTypeGroup(OldDatabaseCase):
    TABLES = """
        CREATE TABLE res_users (id integer PRIMARY KEY, login varchar);
        CREATE TABLE res_groups_users_rel (gid integer, uid integer, PRIMARY KEY (gid, uid));
        INSERT INTO res_users VALUES (1, 'interno'), (2, 'portal'), (3, 'limpio'), (4, 'portal_publico');
    """
    INTERNAL, PORTAL, PUBLIC, BACKEND, OTHER = 10, 11, 12, 20, 30

    def setUp(self):
        super().setUp()
        self.xmlid("base", "group_user", "res.groups", self.INTERNAL)
        self.xmlid("base", "group_portal", "res.groups", self.PORTAL)
        self.xmlid("base", "group_public", "res.groups", self.PUBLIC)
        self.xmlid("portal_backend", "group_portal_backend", "res.groups", self.BACKEND)
        self.cr.execute(
            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, 1), (%s, 1), (%s, 1), (%s, 1), "
            "(%s, 2), (%s, 3), (%s, 3), (%s, 4), (%s, 4)",
            (
                self.INTERNAL, self.PORTAL, self.BACKEND, self.OTHER,
                self.PORTAL,
                self.INTERNAL, self.OTHER,
                self.PORTAL, self.PUBLIC,
            ),
        )

    def groups(self, uid):
        return sorted(gid for (gid,) in self.rows("SELECT gid FROM res_groups_users_rel WHERE uid = %s", (uid,)))

    def test_leaves_one_user_type_and_reports_it(self):
        self.install("portal_backend")
        user_type.migrate(self.cr, "19.0")
        self.assertEqual(self.groups(1), [self.INTERNAL, self.OTHER])
        self.assertEqual(self.groups(2), [self.PORTAL])
        self.assertEqual(self.groups(3), [self.INTERNAL, self.OTHER])
        self.assertEqual(self.groups(4), [self.PORTAL])
        ((type_, message),) = self.logs()
        self.assertEqual(type_, "warning")
        self.assertIn("'interno' pertenecía al grupo 'base.group_portal'", message)
        self.assertIn("'interno' pertenecía al grupo 'portal_backend.group_portal_backend'", message)

    def test_second_run_changes_nothing(self):
        self.install("portal_backend")
        user_type.migrate(self.cr, "19.0")
        before = self.rows("SELECT gid, uid FROM res_groups_users_rel ORDER BY 1, 2")
        user_type.migrate(self.cr, "19.0")
        self.assertEqual(self.rows("SELECT gid, uid FROM res_groups_users_rel ORDER BY 1, 2"), before)
        self.assertEqual(len(self.logs()), 1)

    def test_nothing_without_portal_backend(self):
        user_type.migrate(self.cr, "19.0")
        self.assertEqual(self.groups(1), [self.INTERNAL, self.PORTAL, self.BACKEND, self.OTHER])

    def test_nothing_on_an_upgrade_to_19(self):
        self.install("portal_backend")
        self.write_context(to_version="19.0")
        user_type.migrate(self.cr, "18.0")
        self.assertEqual(self.groups(1), [self.INTERNAL, self.PORTAL, self.BACKEND, self.OTHER])


class TestUniquePaymentMethodLineNames(OldDatabaseCase):
    TABLES = """
        CREATE TABLE account_payment_method_line (
            id serial PRIMARY KEY, journal_id integer, payment_method_id integer, name varchar
        );
        INSERT INTO account_payment_method_line (journal_id, payment_method_id, name) VALUES
            (1, 1, 'Manual'), (1, 1, 'Manual'), (1, 1, 'Manual'), (1, 2, 'Manual'),
            (2, 1, 'Manual'), (NULL, 1, 'Manual'), (NULL, 1, 'Manual');
    """

    def names(self):
        return self.rows("SELECT id, name FROM account_payment_method_line ORDER BY id")

    def test_renames_the_repeated_ones_only(self):
        self.install("account")
        method_lines.migrate(self.cr, "19.0")
        self.assertEqual(
            self.names(),
            [
                (1, "Manual"), (2, "Manual - 1"), (3, "Manual - 2"), (4, "Manual"),
                (5, "Manual"), (6, "Manual"), (7, "Manual"),
            ],
        )

    def test_second_run_changes_nothing(self):
        self.install("account")
        method_lines.migrate(self.cr, "19.0")
        before = self.names()
        method_lines.migrate(self.cr, "19.0")
        self.assertEqual(self.names(), before)

    def test_nothing_without_account(self):
        method_lines.migrate(self.cr, "19.0")
        self.assertEqual(self.names()[1], (2, "Manual"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
