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

# resource_resource is in the schema because user_id and active of hr.employee
# are stored related of resource_id.user_id / resource_id.active in 19.0: a
# schema without it cannot see the resource left behind.
SCHEMA = """
CREATE TABLE res_company (
    id serial PRIMARY KEY,
    name varchar,
    parent_id integer REFERENCES res_company (id)
);
CREATE TABLE resource_resource (
    id serial PRIMARY KEY,
    name varchar,
    user_id integer,
    active boolean DEFAULT true
);
CREATE TABLE hr_employee (
    id serial PRIMARY KEY,
    name varchar,
    company_id integer REFERENCES res_company (id),
    resource_id integer REFERENCES resource_resource (id),
    user_id integer,
    parent_id integer REFERENCES hr_employee (id),
    coach_id integer REFERENCES hr_employee (id),
    active boolean DEFAULT true,
    CONSTRAINT hr_employee_user_uniq UNIQUE (user_id, company_id)
);
CREATE TABLE hr_department (
    id serial PRIMARY KEY,
    name varchar,
    manager_id integer REFERENCES hr_employee (id)
);
CREATE TABLE hr_leave (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE hr_leave_allocation (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE hr_attendance (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE hr_expense (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE account_analytic_line (id serial PRIMARY KEY, employee_id integer);
CREATE TABLE hr_version (
    id serial PRIMARY KEY,
    employee_id integer,
    contract_date_start date
);
"""

# (id, name, company, user, active) -- the people of the scenario, before any
# history. Each one gets a resource of the same id, as hr.employee has.
EMPLOYEES = [
    (10, "Carlos", PARENT, 9, True),
    (11, "Carlos (2)", BRANCH_A, 9, True),
    (12, "Dardo", PARENT, 7, True),
    (13, "Dardo (2)", BRANCH_A, 7, True),
    (14, "Subordinate", BRANCH_A, None, True),
    (15, "Coached", BRANCH_A, None, True),
    (16, "Ana", PARENT, 5, True),
    (17, "Ana (2)", BRANCH_B, 5, True),
    (18, "No user", BRANCH_A, None, True),
    (19, "Outsider", OUTSIDER, 9, True),
    # Moved to the branch: the file of the parent is the archived one.
    (20, "Elsa", PARENT, 3, False),
    (21, "Elsa (2)", BRANCH_A, 3, True),
    # The same person copied in BOTH branches, on top of the parent file.
    (22, "Omar", PARENT, 4, True),
    (23, "Omar (2)", BRANCH_A, 4, True),
    (24, "Omar (3)", BRANCH_B, 4, True),
    (25, "Omar's subordinate", BRANCH_B, None, True),
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
        # The resource carries the user and the active flag; the employee holds
        # the stored copy of both, same as 19.0.
        self.cr.executemany(
            "INSERT INTO resource_resource (id, name, user_id, active)"
            " VALUES (%s, %s, %s, %s)",
            [(emp[0], emp[1], emp[3], emp[4]) for emp in EMPLOYEES],
        )
        self.cr.executemany(
            "INSERT INTO hr_employee"
            " (id, name, company_id, user_id, active, resource_id)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [(emp[0], emp[1], emp[2], emp[3], emp[4], emp[0]) for emp in EMPLOYEES],
        )
        # Dardo's branch copy is manager of one employee, coach of another and
        # head of a department.
        self.cr.execute("UPDATE hr_employee SET parent_id = 13 WHERE id = 14")
        self.cr.execute("UPDATE hr_employee SET coach_id = 13 WHERE id = 15")
        self.cr.execute(
            "INSERT INTO hr_department (id, name, manager_id) VALUES (1, 'Ventas', 13)"
        )
        # Omar's copy in the second branch is manager of somebody too: with two
        # copies plus the parent file, whoever stays has to be the parent one.
        self.cr.execute("UPDATE hr_employee SET parent_id = 24 WHERE id = 25")

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

    def resource(self, employee_id):
        self.cr.execute(
            "SELECT res.user_id, res.active"
            "  FROM resource_resource res"
            "  JOIN hr_employee emp ON emp.resource_id = res.id"
            " WHERE emp.id = %s",
            (employee_id,),
        )
        return dict(zip(("user_id", "active"), self.cr.fetchone()))

    def department(self, department_id):
        self.cr.execute(
            "SELECT manager_id FROM hr_department WHERE id = %s", (department_id,)
        )
        return self.cr.fetchone()[0]

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

    def test_the_resource_of_the_copy_is_freed_and_archived_too(self):
        """user_id and active are stored related of the resource in 19.0.

        Freeing only hr_employee leaves the user with a second resource in the
        parent, and any ORM write on it gives the copy its user back or wakes
        it up again.
        """
        self.preprocess()
        self.assertIsNone(self.resource(11)["user_id"])
        self.assertFalse(self.resource(11)["active"])
        self.assertEqual(self.resource(10)["user_id"], 9)
        self.assertTrue(self.resource(10)["active"])

    def test_manager_and_coach_move_to_the_parent_file(self):
        self.preprocess()
        self.assertEqual(self.employee(14)["parent_id"], 12)
        self.assertEqual(self.employee(15)["coach_id"], 12)

    def test_the_department_it_led_moves_to_the_parent_file(self):
        """An archived employee as head of a department leaves it hanging."""
        self.preprocess()
        self.assertEqual(self.department(1), 12)

    def test_with_the_parent_file_archived_nothing_is_archived(self):
        """Somebody who moved to the branch: there the active file is the copy.

        Archiving it would leave the person with no active file and their
        subordinates pointing at an archived one, so the copy keeps the user
        and stays, and the archived file of the parent is the one freed.
        """
        self.preprocess()
        self.move_to_parent()
        self.assertEqual(self.employee(21)["user_id"], 3)
        self.assertTrue(self.employee(21)["active"])
        self.assertIsNone(self.employee(20)["user_id"])
        self.assertIsNone(self.resource(20)["user_id"])

    def test_with_two_branch_copies_the_parent_file_is_the_one_that_stays(self):
        """The keeper cannot be another copy: it is freed and archived as well.

        Both copies point at the parent file, which is the one that keeps the
        user; a copy chosen as keeper would leave the subordinate hanging from
        an archived file. This one pins the choice instead of reproducing a
        failure: before, the planner picked either, so the same scenario could
        come out right or wrong on the same code.
        """
        self.preprocess()
        self.assertEqual(self.employee(22)["user_id"], 4)
        self.assertTrue(self.employee(22)["active"])
        self.assertIsNone(self.employee(23)["user_id"])
        self.assertIsNone(self.employee(24)["user_id"])
        self.assertFalse(self.employee(23)["active"])
        self.assertFalse(self.employee(24)["active"])
        self.assertEqual(self.employee(25)["parent_id"], 22)

    def test_a_copy_with_time_off_is_freed_but_not_archived(self):
        self.give_history("hr_leave", 17)
        self.preprocess()
        self.assertIsNone(self.employee(17)["user_id"])
        self.assertTrue(self.employee(17)["active"])

    def test_a_copy_with_timesheets_is_not_archived(self):
        self.give_history("account_analytic_line", 11)
        self.preprocess()
        self.assertTrue(self.employee(11)["active"])

    def test_attendances_allocations_and_expenses_are_history_too(self):
        """Three copies, one table each: none of them can be archived."""
        self.give_history("hr_attendance", 11)
        self.give_history("hr_expense", 13)
        self.give_history("hr_leave_allocation", 17)
        self.preprocess()
        for employee_id in (11, 13, 17):
            with self.subTest(employee=employee_id):
                self.assertTrue(self.employee(employee_id)["active"])
                self.assertTrue(self.resource(employee_id)["active"])

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
        self.assertEqual(self.resource(19)["user_id"], 9)
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
        before = [
            (self.employee(emp[0]), self.resource(emp[0])) for emp in EMPLOYEES
        ]

        self.preprocess()
        self.move_to_parent()
        self.assertEqual(
            [(self.employee(emp[0]), self.resource(emp[0])) for emp in EMPLOYEES],
            before,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
