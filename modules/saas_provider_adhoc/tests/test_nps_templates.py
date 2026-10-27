"""The post-migration of saas_provider_adhoc 20.0 that changes t-esc into t-out in the NPS templates.

The tests create and drop their own Postgres database with the tables the script touches, so
they need no Odoo running, only importable, in the target version (20.0 or later).

    /home/odoo/venv/bin/python modules/saas_provider_adhoc/tests/test_nps_templates.py

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
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_saas_provider_adhoc_nps_test")
SCRIPT = os.path.join(REPO, "modules", "saas_provider_adhoc", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

import psycopg2  # noqa: E402
from odoo.tools import SQL  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("saas_provider_adhoc_post_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()


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


ARCH_19 = '<t t-name="x"><p><strong><t t-esc="record.nps_question"/></strong></p><label t-esc="i"/></t>'
ARCH_20 = '<t t-name="x"><p><strong><t t-out="record.nps_question"/></strong></p><label t-out="i"/></t>'


class NpsTemplatesCase(unittest.TestCase):
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
        self.cr.execute("DROP TABLE IF EXISTS ir_ui_view, ir_model_data")
        self.cr.execute(
            """
            CREATE TABLE ir_ui_view (id serial PRIMARY KEY, arch_db jsonb);
            CREATE TABLE ir_model_data (
                id serial PRIMARY KEY, module varchar, name varchar, model varchar, res_id integer
            )
            """
        )

    def _view(self, module, name, arch):
        self.cr.execute("INSERT INTO ir_ui_view (arch_db) VALUES (%s) RETURNING id", [json.dumps(arch)])
        view_id = self.cr.fetchone()[0]
        self.cr.execute(
            "INSERT INTO ir_model_data (module, name, model, res_id) VALUES (%s, %s, 'ir.ui.view', %s)",
            [module, name, view_id],
        )
        return view_id

    def _arch(self, view_id):
        self.cr.execute("SELECT arch_db FROM ir_ui_view WHERE id = %s", [view_id])
        return self.cr.fetchone()[0]

    def test_every_language_of_the_three_templates(self):
        """Each NPS template renders its question in 20, in every language of the arch."""
        ids = [
            self._view("saas_provider_adhoc", name, {"en_US": ARCH_19, "es_419": ARCH_19.replace("x", "y")})
            for name in script.NPS_TEMPLATES
        ]
        script.migrate(self.cr, "19.0.1.0.0")
        for view_id in ids:
            self.assertEqual(self._arch(view_id), {"en_US": ARCH_20, "es_419": ARCH_20.replace("x", "y")})

    def test_other_views_stay(self):
        """Only the NPS templates change: another view of the module, or one with the same name in another
        module, keeps its t-esc."""
        other = self._view("saas_provider_adhoc", "portal_my_home", {"en_US": ARCH_19})
        same_name = self._view("other_module", "nps_template_form", {"en_US": ARCH_19})
        script.migrate(self.cr, "19.0.1.0.0")
        self.assertEqual(self._arch(other), {"en_US": ARCH_19})
        self.assertEqual(self._arch(same_name), {"en_US": ARCH_19})

    def test_the_rest_of_the_arch_stays(self):
        """A template edited in the database keeps its edits: only the directive changes."""
        edited = ARCH_19.replace("<p>", '<p class="edited">Malo ')
        view_id = self._view("saas_provider_adhoc", "nps_16_template_form", {"en_US": edited})
        script.migrate(self.cr, "19.0.1.0.0")
        self.assertEqual(self._arch(view_id), {"en_US": edited.replace("t-esc=", "t-out=")})

    def test_second_run_changes_nothing(self):
        """A second -u leaves the templates as the first one did."""
        view_id = self._view("saas_provider_adhoc", "nps_template_form", {"en_US": ARCH_19})
        script.migrate(self.cr, "19.0.1.0.0")
        script.migrate(self.cr, "19.0.1.0.0")
        self.assertEqual(self.cr.rowcount, 0)
        self.assertEqual(self._arch(view_id), {"en_US": ARCH_20})


if __name__ == "__main__":
    unittest.main()
