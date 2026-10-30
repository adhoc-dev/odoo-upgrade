"""The payment tolerance of the reconcile models moved to the native one of 20, case by case.

The tests create and drop their own Postgres database with the table the script touches, so
they need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/account_statement_base_ux/tests/test_payment_tolerance_to_matching_rule.py

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
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_payment_tolerance_test")
SCRIPT = os.path.join(REPO, "modules", "account_statement_base_ux", "20.0.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from odoo.tools import SQL  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("account_statement_base_ux_post_migration", SCRIPT)
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


class TestPaymentToleranceToMatchingRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        subprocess.run(["createdb", "-E", "UTF8", "-T", "template0", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = Cursor(self.conn.cursor())
        self.cr.execute("DROP TABLE IF EXISTS account_reconcile_model")
        # What the -u leaves: the columns of 20, with the defaults the standard gives them.
        self.cr.execute(
            """
            CREATE TABLE account_reconcile_model (
                id serial PRIMARY KEY,
                name jsonb NOT NULL,
                "trigger" varchar,
                payment_tolerance double precision NOT NULL DEFAULT 0.0,
                payment_tolerance_type varchar NOT NULL DEFAULT 'percentage',
                rule_type varchar DEFAULT 'reco_model'
            )
            """
        )

    def tearDown(self):
        self.cr.close()
        self.conn.rollback()

    def model(self, name, trigger, tolerance):
        self.cr.execute(
            "INSERT INTO account_reconcile_model (name, \"trigger\", payment_tolerance) VALUES (%s, %s, %s) RETURNING id",
            ('{"en_US": "%s"}' % name, trigger, tolerance),
        )
        return self.cr.fetchone()[0]

    def read(self, model_id):
        self.cr.execute(
            'SELECT rule_type, payment_tolerance_type, payment_tolerance, "trigger" FROM account_reconcile_model WHERE id = %s',
            (model_id,),
        )
        return self.cr.fetchone()

    def test_automatic_with_tolerance_becomes_a_matching_rule_in_amount(self):
        model_id = self.model("auto", "auto_reconcile", 50.0)
        script.migrate(self.cr, "19.0.1.5.0")
        self.assertEqual(self.read(model_id), ("matching_rule", "amount", 50.0, "auto_reconcile"))

    def test_manual_with_tolerance_loses_it_and_is_reported(self):
        model_id = self.model("manual", "manual", 30.0)
        with mock.patch.object(script, "log_message") as log_message:
            script.migrate(self.cr, "19.0.1.5.0")
        self.assertEqual(self.read(model_id), ("reco_model", "percentage", 0.0, "manual"))
        log_message.assert_called_once()
        self.assertIn("manual", log_message.call_args.args[1])
        self.assertEqual(log_message.call_args.args[2], "warning")

    def test_automatic_without_tolerance_is_left_alone(self):
        model_id = self.model("plain", "auto_reconcile", 0.0)
        with mock.patch.object(script, "log_message") as log_message:
            script.migrate(self.cr, "19.0.1.5.0")
        self.assertEqual(self.read(model_id), ("reco_model", "percentage", 0.0, "auto_reconcile"))
        log_message.assert_not_called()

    def test_a_second_run_changes_nothing(self):
        auto_id = self.model("auto", "auto_reconcile", 50.0)
        manual_id = self.model("manual", "manual", 30.0)
        with mock.patch.object(script, "log_message") as log_message:
            script.migrate(self.cr, "19.0.1.5.0")
            first = (self.read(auto_id), self.read(manual_id))
            script.migrate(self.cr, "19.0.1.5.0")
        self.assertEqual((self.read(auto_id), self.read(manual_id)), first)
        log_message.assert_called_once()

    def test_a_database_without_the_columns_of_20_is_skipped(self):
        self.cr.execute("ALTER TABLE account_reconcile_model DROP COLUMN rule_type")
        model_id = self.model("auto", "auto_reconcile", 50.0)
        script.migrate(self.cr, "19.0.1.5.0")
        self.cr.execute("SELECT payment_tolerance, payment_tolerance_type FROM account_reconcile_model WHERE id = %s", (model_id,))
        self.assertEqual(self.cr.fetchone(), (50.0, "percentage"))


if __name__ == "__main__":
    unittest.main()
