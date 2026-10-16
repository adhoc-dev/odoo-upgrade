#!/usr/bin/env python3
"""Static checks on modules/base/19.0.0.0/end-migration.py that need no Odoo.

A helper defined twice at module level is silently shadowed by the last
definition. `table_exists` was defined twice and the permissive copy won, so the
FK remap tried to UPDATE SQL views such as hr_employee_public.

Run by hand, this repo has no test runner:

    python3 tests/base/test_end_migration_helpers.py
"""

import ast
import collections
import os
import unittest

PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "modules",
    "base",
    "19.0.0.0",
    "end-migration.py",
)


class FakeCursor:
    def __init__(self):
        self.query = None

    def execute(self, query, params=None):
        self.query = query

    def fetchone(self):
        return (True,)


class TestEndMigrationHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH) as f:
            cls.tree = ast.parse(f.read())

    def test_no_helper_defined_twice(self):
        names = collections.Counter(
            node.name for node in self.tree.body if isinstance(node, ast.FunctionDef)
        )
        duplicated = sorted(name for name, count in names.items() if count > 1)
        self.assertEqual(duplicated, [])

    def test_table_exists_ignores_views(self):
        # The last definition is the one Python keeps
        node = [
            n
            for n in self.tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "table_exists"
        ][-1]
        namespace = {}
        exec(compile(ast.Module([node], []), PATH, "exec"), namespace)
        cr = FakeCursor()
        namespace["table_exists"](cr, "hr_employee_public")
        self.assertIn("BASE TABLE", cr.query)


if __name__ == "__main__":
    unittest.main()
