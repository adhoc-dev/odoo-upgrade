"""The channel between a migration script and the upgrade request: what comes in
(``request_context``) and what goes out (``log_message``, ``set_result``, ``set_breaks``).

The tests play the runner: they write the parameter and create the output table the way
``odoo_obaupgrade.py`` does, and check that what the helpers leave is what it reads back.
They create and drop their own Postgres database; Odoo does not need to be running, only
importable.

    /home/odoo/venv/bin/python oba/tests/test_request_channel.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import json
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_request_channel_test")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

if REPO not in odoo.upgrade.__path__:
    odoo.upgrade.__path__.append(REPO)

import psycopg2  # noqa: E402

from odoo.upgrade.oba import log_message, request_context, set_breaks, set_result  # noqa: E402
from odoo.upgrade.oba.output import TABLE  # noqa: E402
from odoo.upgrade.oba.request_context import PARAMETER  # noqa: E402


class RequestChannelCase(unittest.TestCase):
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
        self.cr = self.conn.cursor()
        self.cr.execute("DROP TABLE IF EXISTS ir_config_parameter, %s" % TABLE)
        self.cr.execute("CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text)")
        # As the runner creates it before the -u
        self.cr.execute(
            """
            CREATE TABLE {table} (
                id serial PRIMARY KEY,
                kind varchar NOT NULL,
                payload jsonb NOT NULL,
                create_date timestamp DEFAULT (now() at time zone 'UTC')
            )
            """.format(table=TABLE)
        )

    def rows(self):
        self.cr.execute("SELECT kind, payload FROM %s ORDER BY id" % TABLE)
        return self.cr.fetchall()


class TestRequestContext(RequestChannelCase):
    def write(self, value):
        self.cr.execute("INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, value))

    def test_empty_without_the_parameter(self):
        """A runbot or local -u has no request: the script sees an empty context."""
        self.assertEqual(request_context(self.cr), {})

    def test_reads_what_the_runner_wrote(self):
        context = {"from_version": "18.0", "is_last_in_series": True, "parameters": {"a": 1}}
        self.write(json.dumps(context))
        self.assertEqual(request_context(self.cr), context)

    def test_garbage_is_an_empty_context(self):
        """A value that is not the runner's dict cannot make a script fail: it falls back."""
        self.write("not json")
        self.assertEqual(request_context(self.cr), {})
        self.cr.execute("UPDATE ir_config_parameter SET value = %s", ('["a", "list"]',))
        self.assertEqual(request_context(self.cr), {})


class TestOutput(RequestChannelCase):
    def test_log_message_leaves_the_row_the_runner_reads(self):
        log_message(self.cr, "Módulos desinstalados: ['a']", "warning")
        ((kind, payload),) = self.rows()
        self.assertEqual(kind, "log")
        self.assertEqual(payload["message"], "Módulos desinstalados: ['a']")
        self.assertEqual(payload["type"], "warning")
        # The caller, relative to the repo: here the test itself
        self.assertEqual(payload["migration_script"], "oba/tests/test_request_channel.py")

    def test_info_is_the_default_type(self):
        log_message(self.cr, "todo bien")
        self.assertEqual(self.rows()[0][1]["type"], "info")

    def test_the_type_is_one_the_provider_knows(self):
        with self.assertRaises(ValueError):
            log_message(self.cr, "x", "debug")
        self.assertEqual(self.rows(), [])

    def test_result_and_breaks_have_their_own_kind(self):
        set_result(self.cr, "3 módulos desinstalados")
        set_breaks(self.cr, "sin catálogo")
        self.assertEqual(
            [(kind, payload["message"]) for kind, payload in self.rows()],
            [("result", "3 módulos desinstalados"), ("breaks", "sin catálogo")],
        )
        self.assertEqual(self.rows()[1][1]["migration_script"], "oba/tests/test_request_channel.py")

    def test_without_the_table_nothing_is_written_and_nothing_fails(self):
        """No runner, no table: a script that logs must not break a local -u."""
        self.cr.execute("DROP TABLE %s" % TABLE)
        log_message(self.cr, "nadie escucha")
        set_result(self.cr, "nadie escucha")
        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (TABLE,))
        self.assertIsNone(self.cr.fetchone(), "the helper does not create the table: that is the runner's job")


if __name__ == "__main__":
    unittest.main()
