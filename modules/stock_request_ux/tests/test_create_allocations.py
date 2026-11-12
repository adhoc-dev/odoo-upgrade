"""The allocations of the moves of a backorder, case by case.

The tests create and drop their own Postgres database with the tables the script touches, so
they need no Odoo running, only importable.

    /home/odoo/venv/bin/python modules/stock_request_ux/tests/test_create_allocations.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_stock_request_allocations_test")
SCRIPT = os.path.join(REPO, "modules", "stock_request_ux", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

import psycopg2  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("stock_request_ux_post_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

UNIT, DOZEN = 1, 2


class CreateAllocationsCase(unittest.TestCase):
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
            """
            DROP TABLE IF EXISTS stock_request_allocation, stock_request, stock_move, stock_picking,
                                 product_product, product_template;
            CREATE TABLE product_template (id serial PRIMARY KEY, uom_id integer);
            CREATE TABLE product_product (id serial PRIMARY KEY, product_tmpl_id integer);
            CREATE TABLE stock_picking (id serial PRIMARY KEY, backorder_id integer);
            CREATE TABLE stock_move (
                id serial PRIMARY KEY,
                picking_id integer,
                product_id integer,
                product_qty numeric,
                state varchar,
                origin_returned_move_id integer
            );
            CREATE TABLE stock_request (id serial PRIMARY KEY, product_id integer, product_uom_id integer, company_id integer);
            CREATE TABLE stock_request_allocation (
                id serial PRIMARY KEY,
                stock_request_id integer,
                stock_move_id integer,
                company_id integer,
                requested_product_uom_qty numeric,
                allocated_product_qty numeric,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            );
            INSERT INTO product_template (uom_id) VALUES (%s);
            INSERT INTO product_product (product_tmpl_id) VALUES (1);
            """,
            (UNIT,),
        )

    def picking(self, backorder_id=None):
        self.cr.execute("INSERT INTO stock_picking (backorder_id) VALUES (%s) RETURNING id", (backorder_id,))
        return self.cr.fetchone()[0]

    def move(self, picking_id, qty, state, returned=None):
        self.cr.execute(
            "INSERT INTO stock_move (picking_id, product_id, product_qty, state, origin_returned_move_id) "
            "VALUES (%s, 1, %s, %s, %s) RETURNING id",
            (picking_id, qty, state, returned),
        )
        return self.cr.fetchone()[0]

    def request(self, uom=UNIT):
        self.cr.execute("INSERT INTO stock_request (product_id, product_uom_id, company_id) VALUES (1, %s, 1) RETURNING id", (uom,))
        return self.cr.fetchone()[0]

    def allocate(self, request_id, move_id, requested, allocated):
        self.cr.execute(
            "INSERT INTO stock_request_allocation (stock_request_id, stock_move_id, company_id, "
            "requested_product_uom_qty, allocated_product_qty) VALUES (%s, %s, 1, %s, %s)",
            (request_id, move_id, requested, allocated),
        )

    def allocations(self, move_id):
        self.cr.execute(
            "SELECT stock_request_id, requested_product_uom_qty, allocated_product_qty "
            "FROM stock_request_allocation WHERE stock_move_id = %s ORDER BY id",
            (move_id,),
        )
        return [(request, float(requested), float(allocated)) for request, requested, allocated in self.cr.fetchall()]

    def partial_delivery(self, requested=5.0, delivered=3.0):
        """A line asks for ``requested``, ``delivered`` is done and the rest waits in a backorder."""
        request = self.request()
        done_picking = self.picking()
        done_move = self.move(done_picking, delivered, "done")
        self.allocate(request, done_move, requested, delivered)
        pending_picking = self.picking(backorder_id=done_picking)
        pending_move = self.move(pending_picking, requested - delivered, "assigned")
        return request, done_move, pending_move, pending_picking


class TestPendingMoves(CreateAllocationsCase):
    def test_pending_move_takes_what_was_open(self):
        request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        self.assertEqual(script.create_allocations(self.cr), [request])
        self.assertEqual(self.allocations(pending), [(request, 2.0, 0.0)])

    def test_each_line_of_a_shared_move_takes_its_own_open_quantity(self):
        line_a, line_b = self.request(), self.request()
        done_picking = self.picking()
        done_move = self.move(done_picking, 6.0, "done")
        self.allocate(line_a, done_move, 5.0, 3.0)
        self.allocate(line_b, done_move, 5.0, 3.0)
        pending = self.move(self.picking(backorder_id=done_picking), 4.0, "assigned")
        self.assertEqual(script.create_allocations(self.cr), sorted([line_a, line_b]))
        self.assertEqual(self.allocations(pending), [(line_a, 2.0, 0.0), (line_b, 2.0, 0.0)])

    def test_a_line_that_was_fully_delivered_takes_nothing(self):
        line_a, line_b = self.request(), self.request()
        done_picking = self.picking()
        done_move = self.move(done_picking, 8.0, "done")
        self.allocate(line_a, done_move, 5.0, 5.0)
        self.allocate(line_b, done_move, 5.0, 3.0)
        pending = self.move(self.picking(backorder_id=done_picking), 2.0, "assigned")
        script.create_allocations(self.cr)
        self.assertEqual(self.allocations(pending), [(line_b, 2.0, 0.0)])


class TestChainOfBackorders(CreateAllocationsCase):
    def test_a_pending_move_received_in_part_counts_what_was_received(self):
        request, _done, middle, middle_picking = self.partial_delivery(5.0, 3.0)
        self.cr.execute("UPDATE stock_move SET state = 'done', product_qty = 1 WHERE id = %s", (middle,))
        last = self.move(self.picking(backorder_id=middle_picking), 1.0, "assigned")
        self.assertEqual(script.create_allocations(self.cr), [request])
        # the middle move was asked for 2 and delivered 1; the last one waits for the other
        self.assertEqual(self.allocations(middle), [(request, 2.0, 1.0)])
        self.assertEqual(self.allocations(last), [(request, 1.0, 0.0)])


class TestWhatIsLeftAlone(CreateAllocationsCase):
    def test_quantity_that_does_not_match_is_left_and_told(self):
        _request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        self.cr.execute("UPDATE stock_move SET product_qty = 5 WHERE id = %s", (pending,))
        with self.assertLogs(script._logger, "WARNING") as logs:
            self.assertEqual(script.create_allocations(self.cr), [])
        self.assertEqual(self.allocations(pending), [])
        self.assertIn(str([pending]), logs.output[0])

    def test_pending_move_smaller_than_what_was_open_is_left(self):
        """A pending move has to take all that was open: if not, part of it went somewhere else."""
        _request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        self.cr.execute("UPDATE stock_move SET product_qty = 1 WHERE id = %s", (pending,))
        with self.assertLogs(script._logger, "WARNING"):
            self.assertEqual(script.create_allocations(self.cr), [])
        self.assertEqual(self.allocations(pending), [])

    def test_request_in_another_unit_is_left(self):
        _request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        self.cr.execute("UPDATE stock_request SET product_uom_id = %s", (DOZEN,))
        with self.assertLogs(script._logger, "WARNING"):
            script.create_allocations(self.cr)
        self.assertEqual(self.allocations(pending), [])

    def test_two_pending_moves_for_the_same_source_are_left(self):
        _request, done, pending, picking = self.partial_delivery(5.0, 3.0)
        twin = self.move(picking, 2.0, "assigned")
        with self.assertLogs(script._logger, "WARNING"):
            script.create_allocations(self.cr)
        self.assertEqual(self.allocations(pending), [])
        self.assertEqual(self.allocations(twin), [])

    def test_returns_and_cancelled_moves_are_not_touched(self):
        _request, done, pending, picking = self.partial_delivery(5.0, 3.0)
        returned = self.move(picking, 1.0, "assigned", returned=done)
        self.cr.execute("UPDATE stock_move SET state = 'cancel' WHERE id = %s", (pending,))
        script.create_allocations(self.cr)
        self.assertEqual(self.allocations(returned), [])
        self.assertEqual(self.allocations(pending), [])

    def test_a_move_that_has_its_allocation_is_not_given_another(self):
        request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        self.allocate(request, pending, 2.0, 0.0)
        self.assertEqual(script.create_allocations(self.cr), [])
        self.assertEqual(self.allocations(pending), [(request, 2.0, 0.0)])

    def test_a_second_run_changes_nothing(self):
        request, _done, pending, _picking = self.partial_delivery(5.0, 3.0)
        script.create_allocations(self.cr)
        self.assertEqual(script.create_allocations(self.cr), [])
        self.assertEqual(self.allocations(pending), [(request, 2.0, 0.0)])


if __name__ == "__main__":
    unittest.main()
