"""The value adjustments of 19 in the fields of Odoo 20, case by case.

The tests create and drop their own Postgres database with the tables the scripts touch, so
they need no Odoo running, only importable. The quantity on hand is injected: it comes from
the ORM, which the test does not have.

    /home/odoo/venv/bin/python modules/stock_account_ux/tests/test_20_product_value.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import contextlib
import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "20.0.1.0.0",
)
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_product_value_test")

try:
    import odoo.upgrade  # noqa: E402, F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402, F401

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402


def _load(name):
    """Load a script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(FOLDER, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pre_migration = _load("pre-migration")
post_migration = _load("post-migration")


class Cursor:
    """The part of the Odoo cursor the scripts use, over a plain psycopg2 one."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if hasattr(query, "_sql_tuple"):
            query, params = query._sql_tuple[:2]
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)

    def dictfetchall(self):
        columns = [column.name for column in self._cr.description]
        return [dict(zip(columns, row)) for row in self._cr.fetchall()]

    @contextlib.contextmanager
    def savepoint(self):
        self._cr.execute("SAVEPOINT test")
        try:
            yield
        except Exception:
            self._cr.execute("ROLLBACK TO SAVEPOINT test")
            raise
        else:
            self._cr.execute("RELEASE SAVEPOINT test")


class ProductValueCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        # UTF8 from template0: a template1 in SQL_ASCII cannot take everything
        subprocess.run(["createdb", "-E", "UTF8", "-T", "template0", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        # One transaction per case, rolled back at the end: the savepoint needs it
        self.addCleanup(self.conn.rollback)
        self.cr = Cursor(self.conn.cursor())
        self.cr.execute("DROP TABLE IF EXISTS product_value, stock_move")
        self.cr.execute(
            """
            CREATE TABLE stock_move (id serial PRIMARY KEY, value numeric);
            CREATE TABLE product_value (
                id serial PRIMARY KEY,
                move_id integer,
                product_id integer,
                lot_id integer,
                company_id integer,
                date timestamp,
                value numeric NOT NULL,
                previous_value numeric,
                old_value numeric DEFAULT 0,
                new_value numeric DEFAULT 0,
                old_cost numeric,
                new_cost numeric,
                quantity numeric
            )
            """
        )

    def move(self, value):
        self.cr.execute("INSERT INTO stock_move (value) VALUES (%s) RETURNING id", (value,))
        return self.cr.fetchone()[0]

    def adjustment(self, value, previous_value=None, move=None, **odoo_fields):
        """A row as 19 left it, with what Odoo 20 may have written already in ``odoo_fields``."""
        columns = dict(move_id=move, product_id=1, company_id=1, date="2026-01-10", value=value, **odoo_fields)
        columns["previous_value"] = previous_value
        self.cr.execute(
            "INSERT INTO product_value (%s) VALUES (%s) RETURNING id"
            % (", ".join(columns), ", ".join(["%s"] * len(columns))),
            list(columns.values()),
        )
        return self.cr.fetchone()[0]

    def row(self, adjustment_id):
        self.cr.execute(
            "SELECT old_value, new_value, old_cost, new_cost, quantity FROM product_value WHERE id = %s",
            (adjustment_id,),
        )
        return self.cr.fetchone()

    def migrate(self, quantity=10):
        """Run both scripts the way the update does, with the quantity on hand as given."""
        self.quantities = []
        pre_migration.migrate(self.cr, "19.0.1.3.0")
        # What the module update does to the column
        self.cr.execute("ALTER TABLE product_value DROP COLUMN previous_value")

        def get_quantity(row):
            self.quantities.append(row["id"])
            if isinstance(quantity, Exception):
                raise quantity
            return quantity

        post_migration._fill(self.cr, get_quantity)

    # -- Backup ----------------------------------------------------------------
    def test_pre_migration_keeps_previous_value(self):
        adjustment_id = self.adjustment(125, previous_value=100)
        pre_migration.migrate(self.cr, "19.0.1.3.0")
        self.cr.execute("SELECT previous_value_bu FROM product_value WHERE id = %s", (adjustment_id,))
        self.assertEqual(self.cr.fetchone()[0], 100)

    def test_pre_migration_without_the_column_does_nothing(self):
        self.cr.execute("ALTER TABLE product_value DROP COLUMN previous_value")
        pre_migration.migrate(self.cr, "19.0.1.3.0")
        self.cr.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'product_value' AND column_name = 'previous_value_bu'"
        )
        self.assertEqual(self.cr.fetchone()[0], 0)

    def test_post_migration_without_the_backup_does_nothing(self):
        # Reaches `_fill` through `migrate`: no `previous_value_bu`, nothing to read
        adjustment_id = self.adjustment(125, previous_value=100, move=self.move(125))
        post_migration.migrate(self.cr, "20.0.1.0.0")
        self.assertEqual(self.row(adjustment_id), (0, 0, None, None, None))

    # -- Move adjustments --------------------------------------------------------
    def test_move_adjustment_takes_the_previous_value(self):
        # Receipt revalued from 100 to 125: old 100, new 125. If it were left at 0 the report
        # and the closing would not see an adjustment of 25.
        adjustment_id = self.adjustment(125, previous_value=100, move=self.move(125))
        self.migrate()
        self.assertEqual(self.row(adjustment_id), (100, 125, None, None, None))

    def test_outgoing_move_adjustment_keeps_the_sign_of_its_move(self):
        # The move is worth -20 in 20 and the adjustment kept the positive 19 value: old and
        # new have to be negative too, or the adjustment would have the wrong direction.
        adjustment_id = self.adjustment(30, previous_value=20, move=self.move(-30))
        self.migrate()
        self.assertEqual(self.row(adjustment_id), (-20, -30, None, None, None))

    def test_move_adjustment_without_previous_value_starts_from_zero(self):
        # Recorded before the module kept it: its variation is the whole new value.
        adjustment_id = self.adjustment(125, move=self.move(125))
        self.migrate()
        self.assertEqual(self.row(adjustment_id), (0, 125, None, None, None))

    def test_move_adjustment_is_not_asked_for_a_quantity(self):
        self.adjustment(125, previous_value=100, move=self.move(125))
        self.migrate()
        self.assertEqual(self.quantities, [])

    # -- Price changes -----------------------------------------------------------
    def test_price_change_takes_the_costs_and_the_quantity(self):
        # Unit cost from 10 to 13 with 10 on hand: adjustment of 30, what 19 booked.
        adjustment_id = self.adjustment(13, previous_value=10)
        self.migrate(quantity=10)
        self.assertEqual(self.row(adjustment_id), (100, 130, 10, 13, 10))

    def test_first_price_change_starts_from_zero(self):
        # The initial price of a product is the first adjustment, from a cost of 0.
        adjustment_id = self.adjustment(13)
        self.migrate(quantity=4)
        self.assertEqual(self.row(adjustment_id), (0, 52, 0, 13, 4))

    def test_price_change_with_no_variation_is_not_asked_for_a_quantity(self):
        # Same cost before and after: its adjustment is zero whatever the quantity.
        adjustment_id = self.adjustment(0, previous_value=0)
        self.migrate()
        self.assertEqual(self.quantities, [])
        self.assertEqual(self.row(adjustment_id), (0, 0, 0, 0, None))

    def test_price_change_whose_quantity_fails_keeps_its_costs(self):
        # The row is reported and left with no quantity (adjustment zero), but the migration
        # goes on with the others.
        failed = self.adjustment(13, previous_value=10)
        other = self.adjustment(20, previous_value=13)
        self.migrate(quantity=ValueError("no stock history"))
        self.assertEqual(self.row(failed), (0, 0, 10, 13, None))
        self.assertEqual(self.row(other), (0, 0, 13, 20, None))

    # -- What Odoo already filled ------------------------------------------------
    def test_a_row_odoo_already_filled_is_left_alone(self):
        move = self.move(60)
        move_adjustment = self.adjustment(60, previous_value=40, move=move, old_value=50, new_value=60)
        price_change = self.adjustment(13, previous_value=10, old_cost=9, new_cost=12, quantity=5)
        self.migrate()
        self.assertEqual(self.row(move_adjustment), (50, 60, None, None, None))
        self.assertEqual(self.row(price_change), (0, 0, 9, 12, 5))

    def test_a_second_run_changes_nothing(self):
        move_adjustment = self.adjustment(125, previous_value=100, move=self.move(125))
        price_change = self.adjustment(13, previous_value=10)
        self.migrate(quantity=10)
        before = (self.row(move_adjustment), self.row(price_change))
        post_migration._fill(self.cr, lambda row: 99)
        self.assertEqual((self.row(move_adjustment), self.row(price_change)), before)


if __name__ == "__main__":
    unittest.main()
