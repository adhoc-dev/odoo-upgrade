"""What the helpdesk_stock_ux post-migration puts back, case by case.

The test creates and drops its own Postgres database with the tables the script touches, so
it needs no Odoo running and no network, only an importable ``odoo.upgrade``.

    /home/odoo/venv/bin/python modules/helpdesk_stock_ux/tests/test_restore_product_and_lot.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point it at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_helpdesk_stock_ux_test")
SCRIPT = os.path.join(REPO, "modules", "helpdesk_stock_ux", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from odoo.tools import SQL  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402


class Cursor:
    """A psycopg2 cursor that takes ``odoo.tools.SQL``, the way Odoo's own cursor does."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if isinstance(query, SQL):
            query, params, __ = query._sql_tuple
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("helpdesk_stock_ux_post_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()
BACKUP = script.BACKUP_TABLE

# helpdesk_ticket is born again without the two columns and helpdesk_stock_ux adds them, so
# they are here with no values: that is the state the script finds.
SCHEMA = """
    CREATE TABLE product_product (id serial PRIMARY KEY);
    CREATE TABLE stock_lot (id serial PRIMARY KEY);
    CREATE TABLE helpdesk_ticket (
        id serial PRIMARY KEY,
        name varchar,
        product_id integer REFERENCES product_product (id),
        lot_id integer REFERENCES stock_lot (id)
    );
    CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
""".format(output=OUTPUT)

BACKUP_SCHEMA = """
    CREATE TABLE {backup} (id integer PRIMARY KEY, product_id integer, lot_id integer);
""".format(backup=BACKUP)


class RestoreCase(unittest.TestCase):
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
        self.cr.execute(SCHEMA + BACKUP_SCHEMA)

    def product(self):
        self.cr.execute("INSERT INTO product_product DEFAULT VALUES RETURNING id")
        return self.cr.fetchone()[0]

    def lot(self):
        self.cr.execute("INSERT INTO stock_lot DEFAULT VALUES RETURNING id")
        return self.cr.fetchone()[0]

    def ticket(self, name="Ticket"):
        self.cr.execute("INSERT INTO helpdesk_ticket (name) VALUES (%s) RETURNING id", (name,))
        return self.cr.fetchone()[0]

    def backed_up(self, ticket_id, product_id=None, lot_id=None):
        self.cr.execute(
            "INSERT INTO {backup} (id, product_id, lot_id) VALUES (%s, %s, %s)".format(backup=BACKUP),
            (ticket_id, product_id, lot_id),
        )

    def run_script(self):
        script.migrate(self.cr, "19.0.1.2.0")

    def values(self, ticket_id):
        self.cr.execute("SELECT product_id, lot_id FROM helpdesk_ticket WHERE id = %s", (ticket_id,))
        return self.cr.fetchone()

    def warnings(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [p["message"] for (p,) in self.cr.fetchall() if p["type"] == "warning"]


class TestWhatIsRestored(RestoreCase):
    def test_the_product_and_the_lot_come_back(self):
        """The whole point: the ticket had both before the pass and has to have both after,
        with the same records. If they come back empty, the data was lost in the pass.
        """
        product, lot = self.product(), self.lot()
        ticket = self.ticket()
        self.backed_up(ticket, product, lot)

        self.run_script()

        self.assertEqual(self.values(ticket), (product, lot))
        self.assertEqual(self.warnings(), [])

    def test_a_ticket_with_only_a_product_keeps_its_lot_empty(self):
        """Most tickets never had a lot. The script has to put back what was there and not
        invent the other half.
        """
        product = self.product()
        ticket = self.ticket()
        self.backed_up(ticket, product_id=product)

        self.run_script()

        self.assertEqual(self.values(ticket), (product, None))

    def test_a_ticket_outside_the_backup_is_not_touched(self):
        """Preservation: a ticket created after the backup, or one that never had a product,
        has nothing to restore and has to stay as it is.
        """
        ticket = self.ticket()

        self.run_script()

        self.assertEqual(self.values(ticket), (None, None))


class TestWhatCouldNotBeRestored(RestoreCase):
    def test_a_product_that_is_gone_leaves_the_field_empty_and_warns(self):
        """The pass can take the product with it. Writing the old id back would point the
        ticket at a record that is not there, so the field stays empty and it is reported.
        """
        lot = self.lot()
        ticket = self.ticket()
        self.backed_up(ticket, product_id=404, lot_id=lot)

        self.run_script()

        self.assertEqual(self.values(ticket), (None, lot))
        [warning] = self.warnings()
        self.assertIn("1 without their product", warning)
        self.assertIn("0 without their lot", warning)

    def test_a_ticket_that_is_gone_is_not_reported_as_a_loss(self):
        """If the ticket itself did not make it, there is nothing to put back and nothing to
        tell the customer: counting it would inflate the warning with tickets nobody has.
        """
        self.backed_up(404, product_id=405)

        self.run_script()

        self.assertEqual(self.warnings(), [])

    def test_without_the_backup_table_nothing_is_written_and_it_warns(self):
        """This is not "no ticket had a product": it is that nobody looked. Staying silent
        would read as a clean upgrade with every value lost.
        """
        self.cr.execute("DROP TABLE %s" % BACKUP)
        ticket = self.ticket()

        self.run_script()

        self.assertEqual(self.values(ticket), (None, None))
        [warning] = self.warnings()
        self.assertIn("pre_odoo", warning)


class TestRunningItAgain(RestoreCase):
    def test_a_second_run_writes_nothing(self):
        """The backup table survives the first -u, so a repeated one goes over the same
        rows: it has to find them already restored and leave them alone.
        """
        product, lot = self.product(), self.lot()
        ticket = self.ticket()
        self.backed_up(ticket, product, lot)
        self.run_script()

        self.cr.execute(script.RESTORE)

        self.assertEqual(self.cr.rowcount, 0)
        self.assertEqual(self.values(ticket), (product, lot))


if __name__ == "__main__":
    unittest.main()
