"""end-250-check_preprinted_remito_templates.py, case by case.

The tests create and drop their own Postgres database with the tables the script reads and
the output table of the runner, and play the ORM with a small fake, so they need no Odoo
running, only importable. What the render really does with a template is not covered here:
it is tried on a real 20 database (task 80426).

    /home/odoo/venv/bin/python modules/base/tests/test_check_preprinted_remito_templates.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest
from contextlib import contextmanager
from unittest import mock

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_preprinted_remito_templates_test")
SCRIPT = os.path.join(REPO, "modules", "base", "0.0.0", "end-250-check_preprinted_remito_templates.py")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from oba.output import TABLE  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("end_250_check_preprinted_remito_templates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

SCHEMA = """
    CREATE TABLE ir_ui_view (id serial PRIMARY KEY, name varchar, key varchar, active boolean);
    CREATE TABLE stock_picking_type (
        id serial PRIMARY KEY,
        name varchar,
        active boolean,
        l10n_ar_voucher_print_mode varchar,
        l10n_ar_delivery_report_view_id integer REFERENCES ir_ui_view (id)
    );
    CREATE TABLE {output} (
        id serial PRIMARY KEY,
        kind varchar NOT NULL,
        payload jsonb NOT NULL,
        create_date timestamp DEFAULT (now() at time zone 'UTC')
    );
""".format(output=TABLE)


class FakeCursor:
    """The real cursor, plus the ``savepoint`` the Odoo one has."""

    def __init__(self, cr):
        self._cr = cr
        self.savepoints = []

    @contextmanager
    def _savepoint(self):
        self.savepoints.append("open")
        try:
            yield self
        finally:
            self.savepoints.append("closed")

    def savepoint(self):
        return _Closable(self._savepoint())

    def __getattr__(self, name):
        return getattr(self._cr, name)


class _Closable:
    """What ``contextlib.closing`` and ``with`` need from the savepoint."""

    def __init__(self, manager):
        self._manager = manager

    def __enter__(self):
        return self._manager.__enter__()

    def __exit__(self, *exc):
        return self._manager.__exit__(*exc)

    def close(self):
        pass


class Records:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)

    def mapped(self, name):
        return [getattr(self, name)]


class FakeModel:
    def __init__(self, env, name):
        self.env, self.name = env, name

    def with_context(self, **_context):
        return self

    def browse(self, ids):
        if self.name == "ir.ui.view":
            return self.env.views[ids]
        return Records(display_name="Tipo %s" % ids)

    def search(self, _domain, limit=None, order=None):
        return Records(ids=self.env.pickings[:limit])

    def _render_qweb_html(self, report_ref, ids):
        self.env.rendered.append((report_ref, ids))
        error = self.env.render_errors.get(ids[0])
        if error:
            raise error
        return "<html/>", "html"


class FakeView:
    """A view whose check passes unless ``check_error`` says otherwise."""

    def __init__(self, view_id, name, key, active=True, check_error=None):
        self.id, self.name, self.key, self.active = view_id, name, key, active
        self.check_error = check_error

    def _check_xml(self):
        if self.check_error:
            raise self.check_error

    _upgrade_original_check_xml = _check_xml


class FakeEnv:
    def __init__(self, cr, views=(), pickings=(), render_errors=None):
        self.cr = cr
        self.views = {view.id: view for view in views}
        self.pickings = list(pickings)
        self.render_errors = render_errors or {}
        self.rendered = []

    def __getitem__(self, name):
        return FakeModel(self, name)


class CheckPreprintedRemitoTemplatesCase(unittest.TestCase):
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
        self.cr = FakeCursor(self.conn.cursor())
        self.cr.execute("DROP TABLE IF EXISTS stock_picking_type, ir_ui_view, %s" % TABLE)
        self.cr.execute(SCHEMA)
        gate = mock.patch.object(script, "should_run", return_value=True)
        gate.start()
        self.addCleanup(gate.stop)

    def view(self, name="Remito del cliente", key="x.remito", active=True):
        self.cr.execute(
            "INSERT INTO ir_ui_view (name, key, active) VALUES (%s, %s, %s) RETURNING id", (name, key, active)
        )
        return self.cr.fetchone()[0]

    def picking_type(self, view_id, mode="preprinted", active=True):
        self.cr.execute(
            "INSERT INTO stock_picking_type (name, active, l10n_ar_voucher_print_mode, "
            "l10n_ar_delivery_report_view_id) VALUES ('Entregas', %s, %s, %s) RETURNING id",
            (active, mode, view_id),
        )
        return self.cr.fetchone()[0]

    def rows(self):
        self.cr.execute("SELECT kind, payload FROM %s ORDER BY id" % TABLE)
        return self.cr.fetchall()

    def migrate(self, env):
        with mock.patch.object(script.util, "env", return_value=env):
            script.migrate(self.cr, "19.0.1.0.0")

    def fake_env(self, view_id, **kwargs):
        view = kwargs.pop("view", None) or FakeView(view_id, "Remito del cliente", "x.remito")
        return FakeEnv(self.cr, views=[view], **kwargs)

    # --- what is checked -------------------------------------------------------------

    def test_only_active_preprinted_types_are_checked(self):
        used = self.view()
        self.picking_type(used)
        self.picking_type(used)
        self.picking_type(self.view(key="x.autoprinted"), mode="autoprinted")
        self.picking_type(self.view(key="x.archived"), active=False)
        self.cr.execute(script.TEMPLATES)
        ((view_id, type_ids),) = self.cr.fetchall()
        self.assertEqual(view_id, used)
        self.assertEqual(len(type_ids), 2, "a view shared by two types is checked once, for both")

    def test_nothing_to_check_without_templates(self):
        env = self.fake_env(0)
        self.migrate(env)
        self.assertEqual(self.rows(), [])
        self.assertEqual(env.rendered, [])

    def test_without_the_gate_nothing_runs(self):
        self.picking_type(self.view())
        env = self.fake_env(1, pickings=[1])
        with mock.patch.object(script, "should_run", return_value=False):
            self.migrate(env)
        self.assertEqual((self.rows(), env.rendered), ([], []))

    def test_without_the_column_nothing_runs(self):
        self.cr.execute("ALTER TABLE stock_picking_type DROP COLUMN l10n_ar_delivery_report_view_id")
        env = self.fake_env(1)
        self.migrate(env)
        self.assertEqual(self.rows(), [])

    # --- when a template does not work ----------------------------------------------

    def test_a_template_that_renders_leaves_nothing_and_the_render_is_rolled_back(self):
        view_id = self.view()
        self.picking_type(view_id)
        env = self.fake_env(view_id, pickings=[11, 12])
        self.migrate(env)
        self.assertEqual(self.rows(), [])
        self.assertEqual(env.rendered, [("stock.action_report_delivery", [11]), ("stock.action_report_delivery", [12])])

    def test_an_inactive_view_opens_the_task_without_rendering(self):
        view_id = self.view(active=False)
        self.picking_type(view_id)
        inactive = FakeView(view_id, "Remito del cliente", "x.remito", active=False)
        env = self.fake_env(view_id, view=inactive, pickings=[1])
        self.migrate(env)
        (_log, (kind, task)) = self.rows()
        self.assertEqual(kind, "provider_record")
        self.assertIn("desactivada", task["vals"]["description"])
        self.assertEqual(env.rendered, [], "an inactive view does not print: there is nothing to render")

    def test_a_view_that_fails_its_own_check_opens_the_task(self):
        view_id = self.view()
        self.picking_type(view_id)
        view = FakeView(view_id, "Remito del cliente", "x.remito", check_error=ValueError("Element not found"))
        view._upgrade_original_check_xml = view._check_xml
        env = self.fake_env(view_id, view=view, pickings=[1])
        self.migrate(env)
        (_log, (_kind, task)) = self.rows()
        self.assertIn("ValueError: Element not found", task["vals"]["description"])

    def test_a_template_that_fails_with_every_picking_opens_the_task(self):
        view_id = self.view()
        self.picking_type(view_id)
        error = AttributeError("'stock.move' object has no attribute 'product_uom'")
        env = self.fake_env(view_id, pickings=[1, 2], render_errors={1: error, 2: error})
        self.migrate(env)
        (log, (kind, task)) = self.rows()
        self.assertEqual(log[0], "log")
        self.assertEqual(log[1]["type"], "warning")
        self.assertEqual(log[1]["module"], "l10n_ar_preprinted_template")
        self.assertEqual(kind, "provider_record")
        self.assertEqual(task["model"], "project.task")
        self.assertEqual(task["ref"], script.TASK_REF)
        self.assertIn("product_uom", task["vals"]["description"])
        self.assertIn("vincularla a mano", task["vals"]["description"])

    def test_the_task_is_built_as_the_upgrade_line_768_builds_it(self):
        view_id = self.view()
        self.picking_type(view_id)
        env = self.fake_env(view_id, pickings=[1], render_errors={1: KeyError("x")})
        self.migrate(env)
        (_log, (_kind, task)) = self.rows()
        vals = task["vals"]
        self.assertEqual(vals["project_id"], {"$request": "upgrade_project"})
        self.assertEqual(vals["stage_id"], 851)
        self.assertEqual(vals["adhoc_product_id"], 4)
        self.assertEqual(vals["tag_ids"], [[6, 0, [773]]])
        self.assertEqual(vals["user_ids"], [[6, 0, []]], "unassigned, so a consultant takes it")
        self.assertNotIn("ticket_ids", vals, "the provider cannot resolve a marker inside a command")

    def test_a_template_that_fails_only_with_some_pickings_is_not_a_template_problem(self):
        view_id = self.view()
        self.picking_type(view_id)
        env = self.fake_env(view_id, pickings=[1, 2, 3], render_errors={2: KeyError("dato")})
        self.migrate(env)
        self.assertEqual(self.rows(), [])

    def test_without_pickings_only_the_view_check_runs(self):
        view_id = self.view()
        self.picking_type(view_id)
        env = self.fake_env(view_id, pickings=[])
        self.migrate(env)
        self.assertEqual((self.rows(), env.rendered), ([], []))

    def test_two_failing_templates_go_in_one_task(self):
        first, second = self.view(key="x.a"), self.view(key="x.b")
        self.picking_type(first)
        self.picking_type(second)
        error = KeyError("x")
        env = FakeEnv(
            self.cr,
            views=[FakeView(first, "Remito A", "x.a"), FakeView(second, "Remito B", "x.b")],
            pickings=[1],
            render_errors={1: error},
        )
        self.migrate(env)
        kinds = [kind for kind, _payload in self.rows()]
        self.assertEqual(kinds, ["log", "provider_record"])
        description = self.rows()[1][1]["vals"]["description"]
        self.assertIn("Remito A", description)
        self.assertIn("Remito B", description)

    def test_what_comes_from_the_database_is_escaped_in_the_task(self):
        view_id = self.view()
        self.picking_type(view_id)
        view = FakeView(view_id, "<b>Remito</b>", "x.remito")
        env = FakeEnv(self.cr, views=[view], pickings=[1], render_errors={1: KeyError("<script>")})
        self.migrate(env)
        description = self.rows()[1][1]["vals"]["description"]
        self.assertNotIn("<script>", description)
        self.assertNotIn("<b>Remito</b>", description)

    def test_the_error_text_is_the_original_one(self):
        try:
            try:
                raise AttributeError("move.product_uom\nsecond line")
            except AttributeError as inner:
                raise RuntimeError("Error while rendering the template:\n<t t-name='x'>...") from inner
        except RuntimeError as outer:
            self.assertEqual(script._error_text(outer), "AttributeError: move.product_uom")


if __name__ == "__main__":
    unittest.main()
