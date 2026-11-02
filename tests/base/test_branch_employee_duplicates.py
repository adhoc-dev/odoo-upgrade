#!/usr/bin/env python3
"""The duplicated employee files of a branch consolidation, over real SQL.

The same person with an employee in the parent and a copy in the branch -- the
workaround so a branch user could see their own HR -- breaks the
`unique (user_id, company_id)` of hr.employee when HR goes up to the parent.
Fakes prove nothing here: what has to hold is the SQL and the constraint, so
the scenario is built in a throwaway database.

Needs a Postgres to talk to; it skips itself when there is none. Run by hand,
this repo has no test runner:

    python3 tests/base/test_branch_employee_duplicates.py
"""

import importlib.util
import os
import sys
import types
import unittest
import uuid

PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "modules",
    "base",
    "19.0.0.0",
    "end-migration.py",
)

PARENT, BRANCH_A, BRANCH_B, OUTSIDER = 1, 2, 3, 4

SCHEMA = """
CREATE TABLE res_company (
    id serial PRIMARY KEY,
    name varchar,
    parent_id integer REFERENCES res_company (id)
);
CREATE TABLE hr_employee (
    id serial PRIMARY KEY,
    name varchar,
    company_id integer REFERENCES res_company (id),
    user_id integer,
    parent_id integer REFERENCES hr_employee (id),
    coach_id integer REFERENCES hr_employee (id),
    active boolean DEFAULT true,
    CONSTRAINT hr_employee_user_uniq UNIQUE (user_id, company_id)
);
CREATE TABLE hr_leave (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE account_analytic_line (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE hr_version (
    id serial PRIMARY KEY,
    employee_id integer,
    contract_date_start date
);
"""

# (id, name, company, user) -- the people of the scenario, before any history.
EMPLOYEES = [
    (10, "Carlos", PARENT, 9),
    (11, "Carlos (2)", BRANCH_A, 9),
    (12, "Dardo", PARENT, 7),
    (13, "Dardo (2)", BRANCH_A, 7),
    (14, "Subordinate", BRANCH_A, None),
    (15, "Coached", BRANCH_A, None),
    (16, "Ana", PARENT, 5),
    (17, "Ana (2)", BRANCH_B, 5),
    (18, "No user", BRANCH_A, None),
    (19, "Outsider", OUTSIDER, 9),
]

# The move the end-migration does right after the preprocessing.
MOVE_EMPLOYEES_TO_PARENT = """
    UPDATE hr_employee SET company_id = %s
     WHERE company_id IN (SELECT id FROM res_company WHERE parent_id = %s)
"""


def load_end_migration():
    """Imports the script with the Odoo it imports stubbed out."""
    odoo = types.ModuleType("odoo")
    exceptions = types.ModuleType("odoo.exceptions")
    exceptions.UserError = type("UserError", (Exception,), {})
    tools = types.ModuleType("odoo.tools")
    tools.SQL = object
    safe_eval_mod = types.ModuleType("odoo.tools.safe_eval")
    safe_eval_mod.safe_eval = lambda *a, **kw: None
    upgrade = types.ModuleType("odoo.upgrade")
    upgrade.util = types.ModuleType("odoo.upgrade.util")
    stubs = {
        "odoo": odoo,
        "odoo.exceptions": exceptions,
        "odoo.tools": tools,
        "odoo.tools.safe_eval": safe_eval_mod,
        "odoo.upgrade": upgrade,
        "odoo.upgrade.util": upgrade.util,
    }
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("end_migration", PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def connect():
    """A connection to the server the environment points at, or None."""
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        return psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5432"),
            user=os.environ.get("PGUSER", "odoo"),
            password=os.environ.get("PGPASSWORD", "odoo"),
            dbname=os.environ.get("PGDATABASE", "postgres"),
        )
    except Exception:
        return None


SERVER = connect()


@unittest.skipIf(SERVER is None, "no Postgres to build the scenario in")
class TestBranchEmployeeDuplicates(unittest.TestCase):
    """Each test gets its own database, so nothing leaks between them."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_end_migration()
        cls.dbname = "test_branch_dup_%s" % uuid.uuid4().hex[:12]
        SERVER.set_isolation_level(0)
        with SERVER.cursor() as cr:
            cr.execute('CREATE DATABASE "%s"' % cls.dbname)
        import psycopg2

        cls.conn = psycopg2.connect(
            host=SERVER.get_dsn_parameters()["host"],
            port=SERVER.get_dsn_parameters()["port"],
            user=SERVER.get_dsn_parameters()["user"],
            password=os.environ.get("PGPASSWORD", "odoo"),
            dbname=cls.dbname,
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        with SERVER.cursor() as cr:
            cr.execute('DROP DATABASE "%s"' % cls.dbname)

    def setUp(self):
        self.cr = self.conn.cursor()
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.cr.close)
        self.cr.execute(
            "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" + SCHEMA
        )
        self.cr.executemany(
            "INSERT INTO res_company (id, name, parent_id) VALUES (%s, %s, %s)",
            [
                (PARENT, "Matriz", None),
                (BRANCH_A, "Sucursal A", PARENT),
                (BRANCH_B, "Sucursal B", PARENT),
                (OUTSIDER, "Ajena", None),
            ],
        )
        self.cr.executemany(
            "INSERT INTO hr_employee (id, name, company_id, user_id)"
            " VALUES (%s, %s, %s, %s)",
            EMPLOYEES,
        )
        # Dardo's branch copy is manager of one employee and coach of another.
        self.cr.execute("UPDATE hr_employee SET parent_id = 13 WHERE id = 14")
        self.cr.execute("UPDATE hr_employee SET coach_id = 13 WHERE id = 15")

    # -- helpers ----------------------------------------------------------

    def preprocess(self):
        self.module.preprocess_unique_move_conflicts(
            self.cr, "hr.employee", PARENT, BRANCH_A
        )

    def move_to_parent(self):
        self.cr.execute(MOVE_EMPLOYEES_TO_PARENT, (PARENT, PARENT))

    def employee(self, employee_id):
        self.cr.execute(
            "SELECT user_id, active, parent_id, coach_id, company_id"
            "  FROM hr_employee WHERE id = %s",
            (employee_id,),
        )
        return dict(
            zip(("user_id", "active", "parent_id", "coach_id", "company_id"),
                self.cr.fetchone())
        )

    def give_history(self, table, employee_id, **values):
        columns = ["employee_id"] + list(values)
        self.cr.execute(
            "INSERT INTO {} ({}) VALUES ({})".format(
                table, ", ".join(columns), ", ".join(["%s"] * len(columns))
            ),
            [employee_id] + list(values.values()),
        )

    # -- tests ------------------------------------------------------------

    def test_without_the_fix_the_move_hits_the_unique_constraint(self):
        """The bug of the ticket, so the scenario is known to reproduce it."""
        import psycopg2

        with self.assertRaises(psycopg2.errors.UniqueViolation) as caught:
            self.move_to_parent()
        self.assertIn("hr_employee_user_uniq", str(caught.exception))

    def test_the_branch_copy_loses_the_user_and_the_move_passes(self):
        self.preprocess()
        self.move_to_parent()
        self.assertIsNone(self.employee(11)["user_id"])
        self.assertEqual(self.employee(10)["user_id"], 9)
        self.assertEqual(self.employee(11)["company_id"], PARENT)

    def test_the_branch_copy_is_archived_and_the_parent_file_stays_active(self):
        self.preprocess()
        self.assertFalse(self.employee(11)["active"])
        self.assertTrue(self.employee(10)["active"])

    def test_manager_and_coach_move_to_the_parent_file(self):
        self.preprocess()
        self.assertEqual(self.employee(14)["parent_id"], 12)
        self.assertEqual(self.employee(15)["coach_id"], 12)

    def test_a_copy_with_time_off_is_freed_but_not_archived(self):
        self.give_history("hr_leave", 17)
        self.preprocess()
        self.assertIsNone(self.employee(17)["user_id"])
        self.assertTrue(self.employee(17)["active"])

    def test_a_copy_with_timesheets_is_not_archived(self):
        self.give_history("account_analytic_line", 11)
        self.preprocess()
        self.assertTrue(self.employee(11)["active"])

    def test_a_copy_with_a_started_contract_is_not_archived(self):
        self.give_history("hr_version", 11, contract_date_start="2024-01-01")
        self.preprocess()
        self.assertTrue(self.employee(11)["active"])

    def test_a_version_without_a_contract_is_not_history(self):
        """Every employee has a version in 19.0; only a started contract counts."""
        self.give_history("hr_version", 11, contract_date_start=None)
        self.preprocess()
        self.assertFalse(self.employee(11)["active"])

    def test_employees_outside_the_tree_and_without_user_are_untouched(self):
        self.preprocess()
        outsider = self.employee(19)
        self.assertEqual(outsider["user_id"], 9)
        self.assertTrue(outsider["active"])
        self.assertEqual(outsider["company_id"], OUTSIDER)
        self.assertTrue(self.employee(18)["active"])

    def test_a_missing_history_table_does_not_stop_the_archiving(self):
        """A base without hr_holidays has no hr_leave, and that is not an error."""
        self.cr.execute("DROP TABLE hr_leave")
        self.preprocess()
        self.assertFalse(self.employee(11)["active"])

    def test_running_it_twice_changes_nothing(self):
        """migrate_standard_fields lives in step 0-1.2, redone on a resume."""
        self.preprocess()
        self.move_to_parent()
        before = [self.employee(emp[0]) for emp in EMPLOYEES]

        self.preprocess()
        self.move_to_parent()
        self.assertEqual([self.employee(emp[0]) for emp in EMPLOYEES], before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
