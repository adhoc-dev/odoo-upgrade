"""The ARBA certificate and DDJJ of the 19 withholding lines go to their account.payment.withholding.line.

The tests create and drop their own Postgres database with the tables the script touches, so they need no
Odoo running, only importable.

    /home/odoo/venv/bin/python modules/l10n_ar_arba_ws/tests/test_certificates_to_20.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_l10n_ar_arba_ws_test")
SCRIPT = os.path.join(REPO, "modules", "l10n_ar_arba_ws", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402, F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("l10n_ar_arba_ws_post_migration_20", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

DDJJ = 7


class Cursor:
    """A psycopg2 cursor that also takes the ``odoo.tools.SQL`` objects of the script, as Odoo's does."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if hasattr(query, "_sql_tuple"):
            query, params = query._sql_tuple[:2]
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


class CertificatesCase(unittest.TestCase):
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
        self.cr.execute(
            "DROP TABLE IF EXISTS %s, %s, %s, %s"
            % (script.OLD_TABLE, script.NEW_TABLE, script.MAP_TABLE, OUTPUT)
        )
        self.cr.execute(
            """
            CREATE TABLE l10n_ar_payment_withholding (
                id integer PRIMARY KEY, payment_id integer, name varchar,
                l10n_ar_cert_number varchar, l10n_ar_dj_arba_id integer
            );
            CREATE TABLE account_payment_withholding_line (
                id integer PRIMARY KEY, payment_id integer, name varchar,
                l10n_ar_cert_number varchar, l10n_ar_dj_arba_id integer
            );
            CREATE TABLE l10n_ar_payment_withholding_map_bu (
                old_id integer PRIMARY KEY, new_id integer NOT NULL, payment_id integer NOT NULL,
                gross_done boolean NOT NULL DEFAULT FALSE
            );
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            """.format(output=OUTPUT)
        )

    def line(self, old_id, new_id, cert=None, ddjj=None, mapped=True):
        """An old line with its ARBA columns and the new line l10n_ar_tax made of it, with name moved."""
        name = cert or "0001-%08d" % old_id
        self.cr.execute(
            "INSERT INTO l10n_ar_payment_withholding VALUES (%s, %s, %s, %s, %s)",
            (old_id, old_id, name, cert, ddjj),
        )
        if mapped:
            self.cr.execute(
                "INSERT INTO account_payment_withholding_line (id, payment_id, name) VALUES (%s, %s, %s)",
                (new_id, old_id, name),
            )
            self.cr.execute(
                "INSERT INTO l10n_ar_payment_withholding_map_bu VALUES (%s, %s, %s)", (old_id, new_id, old_id)
            )

    def new_lines(self):
        self.cr.execute(
            "SELECT id, l10n_ar_cert_number, l10n_ar_dj_arba_id FROM account_payment_withholding_line ORDER BY id"
        )
        return self.cr.fetchall()

    def logs(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [payload for (payload,) in self.cr.fetchall()]

    def test_informed_lines_keep_certificate_and_ddjj(self):
        self.line(1, 101, cert="2026/00001/00000300", ddjj=DDJJ)
        self.line(2, 102)
        # a line of the core 20, not made from a 19 line, is not touched
        self.cr.execute("INSERT INTO account_payment_withholding_line (id, payment_id) VALUES (200, 99)")

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(
            self.new_lines(), [(101, "2026/00001/00000300", DDJJ), (102, None, None), (200, None, None)]
        )
        self.assertEqual(self.logs(), [])

    def test_ddjj_without_certificate_travels(self):
        """A withholding linked to a DDJJ whose certificate did not come back keeps the DDJJ."""
        self.line(1, 101, ddjj=DDJJ)

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(self.new_lines(), [(101, None, DDJJ)])

    def test_second_run_changes_nothing(self):
        self.line(1, 101, cert="2026/00001/00000300", ddjj=DDJJ)
        script.migrate(self.cr, "19.0.1.4.0")
        # informed again in 20, after the first run
        self.cr.execute(
            "UPDATE account_payment_withholding_line SET l10n_ar_cert_number = 'NEW', l10n_ar_dj_arba_id = 8"
        )

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(self.new_lines(), [(101, "NEW", 8)])

    def test_informed_line_not_moved_by_l10n_ar_tax_is_warned(self):
        self.line(1, 101, cert="2026/00001/00000300", ddjj=DDJJ, mapped=False)
        self.line(2, 102, mapped=False)

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(self.new_lines(), [])
        [log] = self.logs()
        self.assertEqual(log["type"], "warning")
        self.assertEqual(log["module"], "l10n_ar_arba_ws")
        self.assertIn("ids [1]", log["message"])

    def test_without_the_map_table_it_stops_with_an_error(self):
        self.line(1, 101, cert="2026/00001/00000300", ddjj=DDJJ)
        self.cr.execute("DROP TABLE l10n_ar_payment_withholding_map_bu")

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(self.new_lines(), [(101, None, None)])
        [log] = self.logs()
        self.assertEqual(log["type"], "error")

    def test_without_the_old_table_it_does_nothing(self):
        self.cr.execute("DROP TABLE l10n_ar_payment_withholding")

        script.migrate(self.cr, "19.0.1.4.0")

        self.assertEqual(self.logs(), [])


if __name__ == "__main__":
    unittest.main()
