"""The pre-migration of base_dynamic_message to 20, case by case.

The tests create and drop their own Postgres database with the tables the script touches,
so they need no Odoo running, only importable, in the target version (20.0 or later).

    /home/odoo/venv/bin/python modules/base_dynamic_message/tests/test_pre_migration.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point them at another checkout or another database.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_base_dynamic_message_test")
SCRIPT = os.path.join(REPO, "modules", "base_dynamic_message", "20.0.1.0.0", "pre-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402
from odoo.tools import SQL  # noqa: E402

from oba.output import TABLE as OUTPUT  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("base_dynamic_message_pre_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

# The code and the compute as the module generates them in 19, for one line.
CODE = """
if rec in rec.filtered_domain(%s):
    messages.append('%s')
"""
COMPUTE = """
for rec in self:
    messages = []
%s
    if not messages:
        rec['x_dynamic_message_1'] = False
    else:
        rec['x_dynamic_message_1'] = "<ul>%%s</ul>" %% "".join(["<li>%%s</li>" %% message for message in messages])
"""


def compute(code):
    return COMPUTE % "\n".join("    " + line if line else line for line in code.split("\n"))


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


class NormalizeOperatorsCase(unittest.TestCase):
    def test_aliases_and_upper_case(self):
        cases = [
            ('[("name", "<>", "x")]', '[("name", "!=", "x")]'),
            ("[('name', '==', 'x')]", "[('name', '=', 'x')]"),
            ('[("name", "ILIKE", "a"), ("id", "NOT IN", [1])]', '[("name", "ilike", "a"), ("id", "not in", [1])]'),
            (
                '["|", ["email", "<>", False], ["phone", "<>", False]]',
                '["|", ["email", "!=", False], ["phone", "!=", False]]',
            ),
        ]
        for old, new in cases:
            with self.subTest(old):
                self.assertEqual(script.normalize_operators(old), new)

    def test_valid_domains_are_left_alone(self):
        for domain in ('[("name", "!=", "x")]', '[("create_date", "<=", "EXP: datetime.datetime.now()")]', "[]", ""):
            with self.subTest(domain):
                self.assertIsNone(script.normalize_operators(domain))

    def test_a_value_like_an_operator_is_not_an_operator(self):
        """'IN' inside a value list must survive: only the second element of a condition is one."""
        self.assertEqual(
            script.normalize_operators('[("ref", "in", ["A", "IN", "B"]), ("name", "<>", "IN")]'),
            '[("ref", "in", ["A", "IN", "B"]), ("name", "!=", "IN")]',
        )

    def test_accents_before_the_operator(self):
        """ast counts bytes: an accent before the operator must not shift the replacement."""
        self.assertEqual(
            script.normalize_operators('[("name", "=", "José"), ("city", "<>", "Córdoba")]'),
            '[("name", "=", "José"), ("city", "!=", "Córdoba")]',
        )

    def test_code_and_compute_keep_their_shape(self):
        code = CODE % ('[("name", "<>", "x")]', "Sin nombre válido")
        self.assertEqual(script.normalize_operators(code), CODE % ('[("name", "!=", "x")]', "Sin nombre válido"))
        self.assertEqual(
            script.normalize_operators(compute(code)), compute(CODE % ('[("name", "!=", "x")]', "Sin nombre válido"))
        )

    def test_unparsable_text_is_left_alone(self):
        self.assertIsNone(script.normalize_operators('[("name", "<>", '))


class MigrateCase(unittest.TestCase):
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
            CREATE TABLE ir_model_fields (id serial PRIMARY KEY, name varchar, state varchar, compute text);
            CREATE TABLE ir_model_dynamic_message (id serial PRIMARY KEY, field_id integer);
            CREATE TABLE ir_model_dynamic_message_line (id serial PRIMARY KEY, domain varchar, code text);
            CREATE TABLE {output} (id serial PRIMARY KEY, kind varchar NOT NULL, payload jsonb NOT NULL);
            """.format(output=OUTPUT)
        )

    def line(self, domain, message="Aviso"):
        code = CODE % (domain, message)
        self.cr.execute(
            "INSERT INTO ir_model_dynamic_message_line (domain, code) VALUES (%s, %s) RETURNING id", (domain, code)
        )
        return self.cr.fetchone()[0], code

    def field(self, compute_, state="manual", linked=True):
        self.cr.execute(
            "INSERT INTO ir_model_fields (name, state, compute) VALUES ('x_dynamic_message_1', %s, %s) RETURNING id",
            (state, compute_),
        )
        field_id = self.cr.fetchone()[0]
        if linked:
            self.cr.execute("INSERT INTO ir_model_dynamic_message (field_id) VALUES (%s)", (field_id,))
        return field_id

    def read(self, table, column, rec_id):
        self.cr.execute(SQL("SELECT %s FROM %s WHERE id = %s", SQL.identifier(column), SQL.identifier(table), rec_id))
        return self.cr.fetchone()[0]

    def request_logs(self):
        self.cr.execute("SELECT payload FROM %s WHERE kind = 'log' ORDER BY id" % OUTPUT)
        return [p["message"] for (p,) in self.cr.fetchall()]

    def migrate(self):
        """Run the script and return what it said about the rewrite in the process log."""
        with self.assertLogs(script._logger.name, "INFO") as logs:
            script.migrate(self.cr, "19.0.1.0.0")
        return [r.getMessage() for r in logs.records if r.getMessage().startswith("Mensajes dinámicos")]

    def test_line_code_and_field_are_rewritten_alike(self):
        line_id, code = self.line('[("email", "<>", False)]', "Tiene email")
        field_id = self.field(compute(code))
        said = self.migrate()
        new_code = CODE % ('[("email", "!=", False)]', "Tiene email")
        self.assertEqual(self.read("ir_model_dynamic_message_line", "domain", line_id), '[("email", "!=", False)]')
        self.assertEqual(self.read("ir_model_dynamic_message_line", "code", line_id), new_code)
        self.assertEqual(self.read("ir_model_fields", "compute", field_id), compute(new_code))
        self.assertEqual(
            said,
            [
                "Mensajes dinámicos: se cambiaron a la forma de 20 los operadores de dominio en 1 líneas, "
                "1 códigos y 1 campos calculados"
            ],
        )
        # an info is for the process log, not for the request
        self.assertEqual(self.request_logs(), [])

    def test_only_the_fields_of_the_messages(self):
        """A manual field that is not a dynamic message, or a field of a module, is not ours."""
        other = self.field("for rec in self: rec.filtered_domain([('a', '<>', 1)])", linked=False)
        base = self.field("for rec in self: rec.filtered_domain([('a', '<>', 1)])", state="base")
        self.migrate()
        self.assertIn("'<>'", self.read("ir_model_fields", "compute", other))
        self.assertIn("'<>'", self.read("ir_model_fields", "compute", base))

    def test_nothing_to_do_and_a_second_run(self):
        line_id, code = self.line('[("email", "!=", False)]')
        self.assertEqual(self.migrate(), [])
        self.assertEqual(self.read("ir_model_dynamic_message_line", "code", line_id), code)

        bad_id, _code = self.line('[("email", "<>", False)]')
        self.assertEqual(len(self.migrate()), 1)
        self.assertEqual(self.migrate(), [])
        self.assertEqual(self.read("ir_model_dynamic_message_line", "domain", bad_id), '[("email", "!=", False)]')


if __name__ == "__main__":
    unittest.main()
