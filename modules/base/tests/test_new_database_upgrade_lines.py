"""The upgrade lines that only touch the new database, as end scripts, case by case.

Covers the scripts that are plain SQL (1470, 1812, 2498 and 2684). The tests create and drop their
own Postgres database with the tables the scripts touch, so they need no Odoo running, only
importable, in the target version (20.0 or later).

    /home/odoo/venv/bin/python modules/base/tests/test_new_database_upgrade_lines.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import contextlib
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
website_menus = _load_script("end-190-drop_new_website_menus.py")


class Cursor:
    """A psycopg2 cursor that also takes the ``SQL`` objects of Odoo, as the migration cursor."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if isinstance(query, SQL):
            query, params, _fields = query._sql_tuple
        return self._cr.execute(query, params)

    @contextlib.contextmanager
    def savepoint(self):
        """The migration cursor has savepoints; psycopg2 in autocommit does not, so the block
        runs in a real transaction and rolls back to the savepoint on error, as Odoo does."""
        conn = self._cr.connection
        autocommit = conn.autocommit
        conn.autocommit = False
        self._cr.execute("SAVEPOINT test_savepoint")
        try:
            yield
        except Exception:
            self._cr.execute("ROLLBACK TO SAVEPOINT test_savepoint")
            raise
        else:
            self._cr.execute("RELEASE SAVEPOINT test_savepoint")
        finally:
            conn.commit()
            conn.autocommit = autocommit

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


class TestWebsiteMenus(NewDatabaseCase):
    TABLES = """
        CREATE TABLE website_menu (
            id serial PRIMARY KEY,
            website_id integer,
            name jsonb,
            parent_id integer REFERENCES website_menu (id) ON DELETE CASCADE
        );
        CREATE TABLE ir_model_data (
            id serial PRIMARY KEY, module varchar, name varchar, model varchar, res_id integer
        );
    """

    def backup(self, *rows):
        """The table the pre-odoo leaves on the old database: every menu, by id."""
        self.cr.execute(
            "CREATE TABLE website_menu_bu (id integer PRIMARY KEY, website_id integer, name varchar)"
        )
        for menu_id, website_id, name in rows:
            self.cr.execute(
                "INSERT INTO website_menu_bu (id, website_id, name) VALUES (%s, %s, %s)",
                (menu_id, website_id, name),
            )

    def menus(self, *rows):
        """Parents first: the foreign key is checked on insert."""
        for menu_id, website_id, name, parent_id in rows:
            self.cr.execute(
                "INSERT INTO website_menu (id, website_id, name, parent_id) VALUES (%s, %s, %s, %s)",
                (menu_id, website_id, json.dumps({"en_US": name}), parent_id),
            )

    def xmlid(self, module, name, res_id):
        self.cr.execute(
            "INSERT INTO ir_model_data (module, name, model, res_id) VALUES (%s, %s, 'website.menu', %s)",
            (module, name, res_id),
        )

    def ids(self):
        return [menu_id for (menu_id,) in self.rows("SELECT id FROM website_menu ORDER BY id")]

    def run_script(self):
        self.install("website")
        website_menus.migrate(self.cr, FROM_VERSION)

    def test_drops_the_item_the_jump_added(self):
        """Website 1 had taken 'Jobs' out and the jump brought it back; website 2 never had it."""
        self.backup((1, 1, "Home"), (2, 2, "Home"))
        self.menus((1, 1, "Home", None), (2, 2, "Home", None), (3, 1, "Jobs", None), (4, 2, "Jobs", None))
        self.run_script()
        self.assertEqual(self.ids(), [1, 2])

    def test_drops_the_twin_of_an_item_that_is_still_there(self):
        """The jump also duplicates the item in the websites that kept it: the copy goes."""
        self.backup((1, 1, "Shop"))
        self.menus((1, 1, "Shop", None), (5, 1, "Shop", None))
        self.run_script()
        self.assertEqual(self.ids(), [1])

    def test_keeps_an_item_recreated_with_another_id(self):
        """Same (website, name) and the backed up id gone: it is that item, not a new one."""
        self.backup((1, 1, "Shop"))
        self.menus((7, 1, "Shop", None))
        self.run_script()
        self.assertEqual(self.ids(), [7])

    def test_drops_the_xmlid_of_what_it_drops(self):
        """Left behind, the next -u of the module would recreate the menu and duplicate it again."""
        self.backup((1, 1, "Home"))
        self.menus((1, 1, "Home", None), (3, 1, "Jobs", None))
        self.xmlid("website_hr_recruitment", "website_menu_jobs", 3)
        self.xmlid("website", "menu_home", 1)
        self.run_script()
        self.assertEqual(self.rows("SELECT module FROM ir_model_data ORDER BY id"), [("website",)])

    def test_leaves_the_menus_without_a_website_alone(self):
        """website.menu.create keeps one copy without website_id when the menu hangs from the
        Default Main Menu: no navbar shows it, and the comparison does not look at it."""
        self.backup((1, 1, "Home"), (9, None, "Jobs"))
        self.menus((1, 1, "Home", None), (9, None, "Jobs", None))
        self.run_script()
        self.assertEqual(self.ids(), [1, 9])

    def test_keeps_a_menu_that_changed_website(self):
        """It is in the backup by id, so it is not new even under another website."""
        self.backup((1, 1, "Home"), (9, None, "Jobs"))
        self.menus((1, 1, "Home", None), (9, 2, "Jobs", None))
        self.run_script()
        self.assertEqual(self.ids(), [1, 9])

    def test_does_not_drop_a_menu_that_holds_an_item_of_the_customer(self):
        """Deleting it would cascade on the child the customer keeps: it is left and reported."""
        self.backup((2, 1, "Offers"))
        self.menus((3, 1, "Jobs", None), (2, 1, "Offers", 3))
        self.run_script()
        self.assertEqual(self.ids(), [2, 3])
        self.assertTrue(any("items del cliente" in m for m in self.logs("warning")))

    def test_does_not_drop_an_ancestor_of_an_item_of_the_customer(self):
        """The cascade reaches the whole subtree, so sparing the direct parent is not enough."""
        self.backup((10, 1, "Offers"))
        self.menus((20, 1, "Jobs", None), (21, 1, "Openings", 20), (10, 1, "Offers", 21))
        self.run_script()
        self.assertEqual(self.ids(), [10, 20, 21])

    def test_reports_when_it_cannot_drop(self):
        """A failed delete is reported on the request and leaves the rest of the -u alone."""
        self.backup((1, 1, "Home"))
        self.menus((1, 1, "Home", None), (3, 1, "Jobs", None))
        self.cr.execute(
            "CREATE TABLE blocker (menu_id integer REFERENCES website_menu (id) ON DELETE RESTRICT);"
            "INSERT INTO blocker (menu_id) VALUES (3)"
        )
        self.run_script()
        self.assertEqual(self.ids(), [1, 3])
        self.assertTrue(any("No se pudieron sacar" in m for m in self.logs("warning")))

    def test_warns_on_the_request_when_there_is_no_backup(self):
        """Nobody looked: dropping menus here would take items the customer did have."""
        self.menus((3, 1, "Jobs", None))
        self.run_script()
        self.assertEqual(self.ids(), [3])
        self.assertTrue(any("No hay respaldo" in m for m in self.logs("warning")))

    def test_nothing_without_website(self):
        self.backup()
        self.menus((3, 1, "Jobs", None))
        website_menus.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.ids(), [3])
        self.assertEqual(self.logs(), [])

    def test_nothing_on_a_minor_update(self):
        self.backup()
        self.menus((3, 1, "Jobs", None))
        self.install("website")
        website_menus.migrate(self.cr, "20.0.1.3")
        self.assertEqual(self.ids(), [3])

    def test_second_run_drops_nothing_again(self):
        """A repeated -u leaves the same rows. The warning about the menu that holds items of
        the customer does come back: it describes the state, and the state is still that one.
        What must not repeat is the action."""
        self.backup((2, 1, "Offers"))
        self.menus((3, 1, "Jobs", None), (2, 1, "Offers", 3), (4, 1, "Events", None))
        self.run_script()
        before = self.ids()
        self.assertEqual(before, [2, 3])
        self.cr.execute("DELETE FROM %s" % OUTPUT)
        website_menus.migrate(self.cr, FROM_VERSION)
        self.assertEqual(self.ids(), before)
        self.assertFalse(any("No se pudieron sacar" in m for m in self.logs()))


if __name__ == "__main__":
    unittest.main()
