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
import json
import logging
import os
import unittest
from unittest import mock

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


class FakeParams:
    """ir.config_parameter over a database that only keeps what was committed."""

    def __init__(self, db):
        self.db = db

    def sudo(self):
        return self

    def get_param(self, key, default=False):
        return self.db.pending.get(key, default)

    def set_param(self, key, value):
        self.db.pending[key] = value


class FakeCr:
    def __init__(self, db):
        self.db = db

    def commit(self):
        self.db.committed = dict(self.db.pending)


class FakeEnv:
    def __init__(self, db):
        self.cr = FakeCr(db)
        self.models = {"ir.config_parameter": FakeParams(db)}

    def __getitem__(self, model):
        return self.models[model]


class FakeDb:
    def __init__(self):
        self.committed = {}
        self.pending = {}

    def env(self):
        """A new run: it only sees what the previous one committed."""
        self.pending = dict(self.committed)
        return FakeEnv(self)


class FakeUserError(Exception):
    pass


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

    def _helpers(self):
        names = {"_done_steps", "step_pending", "step_done"}
        constants = {"PROGRESS_PARAM", "FAIL_AT_STEP_ENV"}
        nodes = [
            n
            for n in self.tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in names)
            or (
                isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id in constants
            )
        ]
        namespace = {
            "json": json,
            "os": os,
            "_logger": logging.getLogger("test"),
            "UserError": FakeUserError,
        }
        exec(compile(ast.Module(nodes, []), PATH, "exec"), namespace)
        return namespace

    def _run(self, h, db, steps, work):
        """A loop shaped like the merge one: each step does its work and commits with its mark."""
        env = db.env()
        for key in steps:
            if h["step_pending"](env, key):
                work.append(key)
                h["step_done"](env, key)

    def test_a_failed_run_resumes_at_the_step_that_broke(self):
        h = self._helpers()
        db = FakeDb()
        steps = ["merge:1:2:0-1.2", "merge:1:2:2:account.tax", "merge:1:2:2:account.group", "merge:1:2:2.1-2.2"]
        first = []
        with mock.patch.dict(os.environ, {h["FAIL_AT_STEP_ENV"]: steps[2]}):
            with self.assertRaises(FakeUserError):
                self._run(h, db, steps, first)
        # The failed step did its work, but it was not committed
        self.assertEqual(first, steps[:3])
        self.assertEqual(json.loads(db.committed[h["PROGRESS_PARAM"]]), steps[:2])

        second = []
        self._run(h, db, steps, second)
        self.assertEqual(second, steps[2:])
        self.assertEqual(json.loads(db.committed[h["PROGRESS_PARAM"]]), steps)

        # A third run finds everything done and touches nothing
        third = []
        self._run(h, db, steps, third)
        self.assertEqual(third, [])

    def test_every_step_opened_is_marked_done(self):
        # A step_pending without its step_done never commits: the next run would repeat it
        for name in ("migrate", "migrate_store_to_branch"):
            node = [
                n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == name
            ][-1]
            keys = collections.defaultdict(collections.Counter)
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in ("step_pending", "step_done")
                ):
                    keys[call.func.id][ast.unparse(call.args[1])] += 1
            self.assertTrue(keys["step_pending"], name)
            self.assertEqual(set(keys["step_pending"]), set(keys["step_done"]), name)


if __name__ == "__main__":
    unittest.main()
