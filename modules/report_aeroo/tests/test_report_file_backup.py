"""La ruta de la plantilla de los reportes Aeroo a través del pase 19→20, caso por caso.

El test crea y borra su propia base de Postgres con las tablas que tocan los scripts, y
simula el pase como lo hace Odoo: borra la columna report_file y el -u la recrea vacía. No
levanta Odoo; solo lo necesita importable.

    /home/odoo/venv/bin/python modules/report_aeroo/tests/test_report_file_backup.py

``ODOO_PATH`` y ``UPGRADE_TEST_DB`` los apuntan a otro checkout o a otra base.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_report_aeroo_report_file_test")
BACKUP_SCRIPT = os.path.join(REPO, "scripts", "pre_odoo", "190_200", "020-backup_aeroo_report_file.py")
RESTORE_SCRIPT = os.path.join(REPO, "modules", "report_aeroo", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from oba.request_context import PARAMETER  # noqa: E402


def _load(name, path):
    """Carga el script por su ruta: una carpeta de versión no es un paquete."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = _load("backup_aeroo_report_file", BACKUP_SCRIPT)
restore = _load("report_aeroo_post_migration", RESTORE_SCRIPT)

BACKUP_TABLE = backup.BACKUP_TABLE


class Cursor:
    """Un cursor que acepta `odoo.tools.SQL`, como el de Odoo."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if hasattr(query, "_sql_tuple"):
            query, params = query._sql_tuple[:2]
        self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


class ReportFileCase(unittest.TestCase):
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
            "DROP TABLE IF EXISTS ir_act_report_xml, ir_module_module, ir_config_parameter, %s" % BACKUP_TABLE
        )
        self.cr.execute(
            """
            CREATE TABLE ir_act_report_xml (
                id serial PRIMARY KEY,
                report_name varchar NOT NULL,
                report_type varchar NOT NULL,
                report_file varchar
            );
            CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
            CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text)
            """
        )
        self.installed("report_aeroo")
        self.context(to_version="20.0")

    def installed(self, *modules):
        for module in modules:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, 'installed')", (module,))

    def context(self, **values):
        """Lo que el runner escribe para el request."""
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (PARAMETER, json.dumps(values)),
        )

    def report(self, report_name, report_type="aeroo", report_file=None):
        self.cr.execute(
            "INSERT INTO ir_act_report_xml (report_name, report_type, report_file) VALUES (%s, %s, %s) RETURNING id",
            (report_name, report_type, report_file),
        )
        return self.cr.fetchone()[0]

    def pass_through_odoo(self):
        """Lo que hace el pase: Odoo borra la columna y nuestro -u la recrea vacía."""
        self.cr.execute("ALTER TABLE ir_act_report_xml DROP COLUMN report_file")
        self.cr.execute("ALTER TABLE ir_act_report_xml ADD COLUMN report_file varchar")

    def report_files(self):
        self.cr.execute("SELECT id, report_file FROM ir_act_report_xml ORDER BY id")
        return dict(self.cr.fetchall())

    def table_exists(self, table):
        self.cr.execute("SELECT to_regclass(%s)", (table,))
        return self.cr.fetchone()[0] is not None

    # el salto completo

    def test_restores_the_path_the_pass_dropped(self):
        aeroo = self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")
        qweb = self.report("sale.order", report_type="qweb-pdf", report_file="sale/report/order.xml")

        backup.migrate(self.cr, "19.0")
        self.pass_through_odoo()
        restore.migrate(self.cr, "20.0.1.0.0")

        self.assertEqual(self.report_files()[aeroo], "picking_waybill/report/waybill.odt")
        # Los qweb no son nuestros: el campo salió del core y no se repone.
        self.assertIsNone(self.report_files()[qweb])

    def test_does_not_overwrite_what_the_update_reloaded(self):
        aeroo = self.report("account_debt_report", report_file="account_debt_report/report/old.odt")

        backup.migrate(self.cr, "19.0")
        self.pass_through_odoo()
        self.cr.execute(
            "UPDATE ir_act_report_xml SET report_file = %s WHERE id = %s",
            ("account_debt_report/report/new.odt", aeroo),
        )
        restore.migrate(self.cr, "20.0.1.0.0")

        self.assertEqual(self.report_files()[aeroo], "account_debt_report/report/new.odt")

    def test_running_the_restore_twice_changes_nothing(self):
        aeroo = self.report("aeroo_sample_report_id", report_file="report_aeroo/report/sample.odt")

        backup.migrate(self.cr, "19.0")
        self.pass_through_odoo()
        restore.migrate(self.cr, "20.0.1.0.0")
        restore.migrate(self.cr, "20.0.1.0.0")

        self.assertEqual(self.report_files()[aeroo], "report_aeroo/report/sample.odt")

    # los gates del respaldo

    def test_backs_up_only_aeroo_reports_with_a_path(self):
        with_path = self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")
        self.report("stock_picking_labels", report_file="")
        self.report("sale.order", report_type="qweb-pdf", report_file="sale/report/order.xml")

        backup.migrate(self.cr, "19.0")

        self.cr.execute("SELECT id FROM %s" % BACKUP_TABLE)
        self.assertEqual([row[0] for row in self.cr.fetchall()], [with_path])

    def test_skips_a_database_without_the_module(self):
        self.cr.execute("DELETE FROM ir_module_module WHERE name = 'report_aeroo'")
        self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")

        backup.migrate(self.cr, "19.0")

        self.assertFalse(self.table_exists(BACKUP_TABLE))

    def test_skips_a_jump_to_another_version(self):
        self.context(to_version="19.0")
        self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")

        backup.migrate(self.cr, "19.0")

        self.assertFalse(self.table_exists(BACKUP_TABLE))

    def test_drops_the_table_of_an_earlier_run_that_does_not_apply(self):
        self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")
        backup.migrate(self.cr, "19.0")
        self.assertTrue(self.table_exists(BACKUP_TABLE))

        self.context(to_version="19.0")
        backup.migrate(self.cr, "19.0")

        self.assertFalse(self.table_exists(BACKUP_TABLE))

    # el gate de la reposición

    def test_without_the_backup_table_it_restores_nothing(self):
        aeroo = self.report("picking_waybill", report_file="picking_waybill/report/waybill.odt")
        self.pass_through_odoo()

        restore.migrate(self.cr, "20.0.1.0.0")

        self.assertIsNone(self.report_files()[aeroo])


if __name__ == "__main__":
    unittest.main()
