"""end-240-drop_foreign_model_mail_template_reports.py, case by case.

The tests create and drop their own Postgres database with the tables the script touches,
and patch the running Odoo version, so they need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/base/tests/test_drop_foreign_model_mail_template_reports.py

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
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_drop_foreign_model_reports_test")
SCRIPT = os.path.join(REPO, "modules", "base", "0.0.0", "end-240-drop_foreign_model_mail_template_reports.py")

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
    spec = importlib.util.spec_from_file_location("end_240_drop_foreign_model_mail_template_reports", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

# The user invitation (res.users) linked to the payment receipt (account.payment).
INVITATION, PAYMENT_TEMPLATE = 2, 10
PAYMENT_RECEIPT, USERS_REPORT = 275, 300
FOREIGN = (INVITATION, PAYMENT_RECEIPT)
OWN = (PAYMENT_TEMPLATE, PAYMENT_RECEIPT)
OWN_ON_USERS = (INVITATION, USERS_REPORT)
KEPT = sorted([OWN, OWN_ON_USERS])
ALL = sorted([FOREIGN, OWN, OWN_ON_USERS])


class DropForeignModelMailTemplateReportsCase(unittest.TestCase):
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
        self.cr.execute(
            "DROP TABLE IF EXISTS ir_module_module, ir_config_parameter, mail_template, ir_act_report_xml, "
            "mail_template_ir_actions_report_rel"
        )
        self.cr.execute(
            """
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
            CREATE TABLE mail_template (id integer PRIMARY KEY, model varchar);
            CREATE TABLE ir_act_report_xml (id integer PRIMARY KEY, model varchar NOT NULL);
            CREATE TABLE mail_template_ir_actions_report_rel (
                mail_template_id integer NOT NULL,
                ir_actions_report_id integer NOT NULL,
                PRIMARY KEY (mail_template_id, ir_actions_report_id)
            );
            """
        )
        self.cr.execute(
            "INSERT INTO mail_template VALUES (%s, 'res.users'), (%s, 'account.payment')", (INVITATION, PAYMENT_TEMPLATE)
        )
        self.cr.execute(
            "INSERT INTO ir_act_report_xml VALUES (%s, 'account.payment'), (%s, 'res.users')",
            (PAYMENT_RECEIPT, USERS_REPORT),
        )
        self.cr.execute(
            "INSERT INTO mail_template_ir_actions_report_rel VALUES (%s, %s), (%s, %s), (%s, %s)",
            FOREIGN + OWN + OWN_ON_USERS,
        )

    def module(self, state="to upgrade"):
        self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES ('mail', %s)", (state,))

    def run_script(self, target=20, version="19.0.1.0.0"):
        with mock.patch.object(release, "version_info", (target, 0, 0, "final", 0, "")):
            script.migrate(self.cr, version)

    def pairs(self):
        self.cr.execute("SELECT mail_template_id, ir_actions_report_id FROM mail_template_ir_actions_report_rel")
        return sorted(self.cr.fetchall())

    def test_report_of_another_model_is_unlinked(self):
        """Only the pair with another model goes; the template keeps its own report."""
        self.module()
        self.run_script()
        self.assertEqual(self.pairs(), KEPT)

    def test_template_without_model_keeps_its_reports(self):
        self.module()
        self.cr.execute("UPDATE mail_template SET model = NULL WHERE id = %s", (INVITATION,))
        self.run_script()
        self.assertEqual(self.pairs(), ALL)

    def test_second_run_changes_nothing(self):
        self.module()
        self.run_script()
        self.run_script()
        self.assertEqual(self.pairs(), KEPT)

    def test_upgrade_to_18_unlinks_too(self):
        self.module()
        self.run_script(target=18, version="17.0.1.0")
        self.assertEqual(self.pairs(), KEPT)

    def test_mail_not_installed_changes_nothing(self):
        self.module("uninstalled")
        self.run_script()
        self.assertEqual(self.pairs(), ALL)

    def test_minor_update_changes_nothing(self):
        self.module("installed")
        self.run_script(version="20.0.1.0.0")
        self.assertEqual(self.pairs(), ALL)


if __name__ == "__main__":
    unittest.main()
