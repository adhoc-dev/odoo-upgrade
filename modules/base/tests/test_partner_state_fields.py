"""The partner_state configuration lines the upgrade removes, from backup to customer note.

Covers scripts/pre_odoo/always/220-backup_partner_state_fields.py and
modules/base/0.0.0/end-220-check_partner_state_fields.py. The tests create and drop their own
Postgres database with the tables the scripts touch, and drop a field to stand for the upgrade,
so they need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/base/tests/test_partner_state_fields.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_partner_state_fields_test")
BACKUP = os.path.join(REPO, "scripts", "pre_odoo", "always", "220-backup_partner_state_fields.py")
CHECK = os.path.join(REPO, "modules", "base", "0.0.0", "end-220-check_partner_state_fields.py")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: F401, E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402
from odoo.tools import SQL  # noqa: E402

from oba.customer_note import TABLE as NOTES  # noqa: E402
from oba.output import TABLE as OUTPUT  # noqa: E402


def _load_script(name, path):
    """Load a script by path: the folders are not packages and the names have dashes."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = _load_script("pre_odoo_220_backup_partner_state_fields", BACKUP)
check = _load_script("end_220_check_partner_state_fields", CHECK)

# res.partner fields of the loaded code in 20: company_registry is not one of them
PARTNER_FIELDS = {"name", "email", "phone"}


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


class PartnerStateFieldsCase(unittest.TestCase):
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
            CREATE TABLE ir_model_fields (id serial PRIMARY KEY, name varchar NOT NULL, field_description jsonb);
            CREATE TABLE res_partner_state_field (
                id serial PRIMARY KEY,
                field_id integer NOT NULL REFERENCES ir_model_fields (id) ON DELETE CASCADE,
                approval boolean, block_edition boolean, track boolean, changes boolean
            );
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            INSERT INTO ir_module_module (name, state) VALUES ('partner_state', 'installed');
            INSERT INTO ir_model_fields (name, field_description) VALUES
                ('name', '{{"en_US": "Name", "es_419": "Nombre"}}'),
                ('company_registry', '{{"en_US": "Company ID"}}');
            INSERT INTO res_partner_state_field (field_id, approval, block_edition, track, changes) VALUES
                (1, true, true, true, false),
                (2, true, false, false, true);
            """.format(output=OUTPUT)
        )

    def upgrade(self, *dropped):
        """What the pass to Odoo does to the lines: the field goes, and the line with it."""
        for name in dropped:
            self.cr.execute("DELETE FROM ir_model_fields WHERE name = %s", (name,))

    def notes(self):
        self.cr.execute("SELECT to_regclass(%s)", (NOTES,))
        if not self.cr.fetchone()[0]:
            return {}
        self.cr.execute("SELECT key, value FROM %s" % NOTES)
        return dict(self.cr.fetchall())

    def logs(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [payload for (payload,) in self.cr.fetchall()]


class TestPartnerStateFields(PartnerStateFieldsCase):
    def test_a_dropped_field_is_told_to_the_customer(self):
        backup.migrate(self.cr, "19.0.1.0.0")
        self.upgrade("company_registry")
        check.run(self.cr, PARTNER_FIELDS)
        notes = self.notes()
        self.assertEqual(notes["partner_state_campos_perdidos_total"], 1)
        self.assertEqual(
            notes["partner_state_campos_perdidos"],
            [
                {
                    "campo": "company_registry",
                    "etiqueta": "Company ID",
                    "requerido_para_aprobar": True,
                    "bloqueado_si_aprobado": False,
                    "vuelve_a_potencial": False,
                    "registra_en_chatter": True,
                }
            ],
        )
        (log,) = self.logs()
        self.assertEqual(log["type"], "warning")
        self.assertIn("['company_registry']", log["message"])

    def test_a_field_dropped_after_the_end_scripts_is_told_too(self):
        """The field of a module that leaves in 20 is still in ir_model_fields here:
        _process_end and end-900 drop it, and the line, after this script."""
        backup.migrate(self.cr, "19.0.1.0.0")
        check.run(self.cr, PARTNER_FIELDS)
        notes = self.notes()
        self.assertEqual(notes["partner_state_campos_perdidos_total"], 1)
        self.assertEqual([line["campo"] for line in notes["partner_state_campos_perdidos"]], ["company_registry"])

    def test_nothing_lost_is_still_emitted(self):
        """The backup was there, so zero is a result the message may want to show."""
        backup.migrate(self.cr, "19.0.1.0.0")
        check.run(self.cr, PARTNER_FIELDS | {"company_registry"})
        self.assertEqual(self.notes(), {"partner_state_campos_perdidos": [], "partner_state_campos_perdidos_total": 0})
        self.assertEqual(self.logs(), [])

    def test_no_backup_emits_nothing(self):
        """Nobody looked: a zero here would tell the customer all is fine without checking."""
        self.upgrade("company_registry")
        check.run(self.cr, PARTNER_FIELDS)
        self.assertEqual(self.notes(), {})

    def test_no_backup_without_the_module(self):
        self.cr.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = 'partner_state'")
        backup.migrate(self.cr, "19.0.1.0.0")
        self.cr.execute("SELECT to_regclass(%s)", (backup.BACKUP_TABLE,))
        self.assertIsNone(self.cr.fetchone()[0])

    def test_a_second_run_gives_the_same_note(self):
        backup.migrate(self.cr, "19.0.1.0.0")
        self.upgrade("company_registry")
        check.run(self.cr, PARTNER_FIELDS)
        first = self.notes()
        check.run(self.cr, PARTNER_FIELDS)
        self.assertEqual(self.notes(), first)


if __name__ == "__main__":
    unittest.main()
