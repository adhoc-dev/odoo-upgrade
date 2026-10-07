"""The upgrade lines that run on the old database before the pass to Odoo, case by case.

Covers 090, 100, 110 and 120 of ``scripts/pre_odoo/always``. The tests create and drop their own
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
team_members = _load_script("110-archive_admin_sales_team_members.py")
deprecated_views = _load_script("120-drop_deprecated_website_views.py")


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


class TestArchiveAdminSalesTeamMembers(OldDatabaseCase):
    TABLES = """
        CREATE TABLE crm_team_member (id serial PRIMARY KEY, user_id integer, active boolean);
        INSERT INTO crm_team_member (user_id, active) VALUES (2, true), (2, false), (5, true);
    """

    def setUp(self):
        super().setUp()
        self.xmlid("base", "user_admin", "res.users", 2)

    def active(self):
        return self.rows("SELECT id, active FROM crm_team_member ORDER BY id")

    def test_archives_the_admin_memberships_only(self):
        team_members.migrate(self.cr, "19.0")
        self.assertEqual(self.active(), [(1, False), (2, False), (3, True)])
        self.assertEqual(self.logs(), [("info", "Archived 1 crm.team.member record(s) for the admin user")])

    def test_second_run_says_there_is_nothing_to_do(self):
        team_members.migrate(self.cr, "19.0")
        team_members.migrate(self.cr, "19.0")
        self.assertEqual(self.logs()[1][1], "No active crm.team.member records found for the admin user, nothing to do")

    def test_nothing_without_the_table(self):
        self.cr.execute("DROP TABLE crm_team_member")
        team_members.migrate(self.cr, "19.0")
        self.assertEqual(self.logs(), [])

    def test_nothing_on_an_upgrade_to_19(self):
        self.write_context(to_version="19.0")
        team_members.migrate(self.cr, "18.0")
        self.assertEqual(self.active(), [(1, True), (2, False), (3, True)])


class TestDropDeprecatedWebsiteViews(OldDatabaseCase):
    # 1 <- 2 <- 3: a deprecated chain. 4: deprecated, a restrict reference points to it.
    # 5 <- 6: deprecated with a child that is not. 7: not deprecated. 8: deprecated, with a page.
    TABLES = """
        CREATE TABLE ir_ui_view (
            id integer PRIMARY KEY, key varchar, active boolean DEFAULT true,
            inherit_id integer REFERENCES ir_ui_view ON DELETE RESTRICT
        );
        CREATE TABLE website_page (id serial PRIMARY KEY, view_id integer REFERENCES ir_ui_view ON DELETE CASCADE);
        CREATE TABLE blocker (id serial PRIMARY KEY, view_id integer REFERENCES ir_ui_view ON DELETE RESTRICT);
        INSERT INTO ir_ui_view (id, key, inherit_id) VALUES
            (1, 'website.a_depreciada', NULL), (2, 'website.b_depreciada', 1), (3, 'website.c_depreciada', 2),
            (4, 'website.d_depreciada', NULL), (5, 'website.e_depreciada', NULL), (6, 'website.f', 5),
            (7, 'website.g', NULL), (8, 'website.h_depreciada', NULL);
        INSERT INTO website_page (view_id) VALUES (8);
        INSERT INTO blocker (view_id) VALUES (4);
    """

    def setUp(self):
        super().setUp()
        self.xmlid("website", "a_depreciada", "ir.ui.view", 1)
        self.xmlid("website", "g", "ir.ui.view", 7)
        # The runner runs the scripts in one transaction, and the script uses savepoints.
        self.cr.execute("BEGIN")

    def tearDown(self):
        self.cr.execute("ROLLBACK")
        super().tearDown()

    def views(self):
        return self.rows("SELECT id, active FROM ir_ui_view ORDER BY id")

    def test_drops_leaves_first_and_archives_what_is_referenced(self):
        self.install("website")
        deprecated_views.migrate(self.cr, "19.0")
        self.assertEqual(self.views(), [(4, False), (5, True), (6, True), (7, True)])
        self.assertEqual(self.rows("SELECT res_id FROM ir_model_data WHERE model = 'ir.ui.view'"), [(7,)])
        self.assertEqual(self.rows("SELECT count(*) FROM website_page"), [(0,)])

    def test_second_run_changes_nothing(self):
        self.install("website")
        deprecated_views.migrate(self.cr, "19.0")
        before = self.views()
        deprecated_views.migrate(self.cr, "19.0")
        self.assertEqual(self.views(), before)

    def test_nothing_without_website(self):
        deprecated_views.migrate(self.cr, "19.0")
        self.assertEqual(len(self.views()), 8)

    def test_nothing_on_an_upgrade_to_19(self):
        self.install("website")
        self.write_context(to_version="19.0")
        deprecated_views.migrate(self.cr, "18.0")
        self.assertEqual(len(self.views()), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
