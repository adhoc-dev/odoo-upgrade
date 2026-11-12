"""end-230-drop_variant_preselect_parameter.py, case by case.

The tests create and drop their own Postgres database with the tables the script touches,
and patch the running Odoo version, so they need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/base/tests/test_drop_variant_preselect_parameter.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest
from unittest import mock

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_drop_variant_preselect_test")
SCRIPT = os.path.join(REPO, "modules", "base", "0.0.0", "end-230-drop_variant_preselect_parameter.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402
from odoo import release  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("end_230_drop_variant_preselect_parameter", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

OTHER = "website_sale.some_other_parameter"


class DropVariantPreselectParameterCase(unittest.TestCase):
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
        self.cr.execute("DROP TABLE IF EXISTS ir_module_module, ir_config_parameter")
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            """
        )
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, 'False'), (%s, 'x')", (script.PARAMETER, OTHER)
        )

    def module(self, state):
        self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, %s)", (script.MODULE, state))

    def run_script(self, target=20, version="19.0.1.0.0"):
        with mock.patch.object(release, "version_info", (target, 0, 0, "final", 0, "")):
            script.migrate(self.cr, version)

    def parameters(self):
        self.cr.execute("SELECT key FROM ir_config_parameter ORDER BY key")
        return [key for (key,) in self.cr.fetchall()]

    def test_module_without_code_drops_the_parameter(self):
        """In 20 the module has no code and stays to upgrade: that is the case it runs for."""
        self.module("to upgrade")
        self.run_script()
        self.assertEqual(self.parameters(), [OTHER])

    def test_second_run_changes_nothing(self):
        self.module("to upgrade")
        self.run_script()
        self.run_script()
        self.assertEqual(self.parameters(), [OTHER])

    def test_module_not_installed_keeps_the_parameter(self):
        self.module("uninstalled")
        self.run_script()
        self.assertEqual(self.parameters(), [OTHER, script.PARAMETER])

    def test_upgrade_to_19_keeps_the_parameter(self):
        self.module("to upgrade")
        self.run_script(target=19, version="18.0.1.0.0")
        self.assertEqual(self.parameters(), [OTHER, script.PARAMETER])

    def test_minor_update_keeps_the_parameter(self):
        self.module("installed")
        self.run_script(version="20.0.1.0.0")
        self.assertEqual(self.parameters(), [OTHER, script.PARAMETER])


if __name__ == "__main__":
    unittest.main()
