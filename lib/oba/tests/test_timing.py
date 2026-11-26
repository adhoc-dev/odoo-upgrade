"""``timed`` logs how long a script took, and every script that runs from 20 on carries it.

Needs no database nor Odoo:

    PYTHONPATH=lib python3 lib/oba/tests/test_timing.py
"""

import ast
import glob
import inspect
import os
import unittest

from oba import timed

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# What runs on a jump from 20 on: 0.0.0 on every jump, the 20 folders, pre_odoo and pre_upgrade
PATTERNS = (
    "modules/*/0.0.0/*.py",
    "modules/*/20.*/*.py",
    "scripts/pre_odoo/always/*.py",
    "scripts/pre_odoo/190_200/*.py",
    "scripts/pre_upgrade/always/*.py",
    "scripts/pre_upgrade/190_200/*.py",
)


def migrate(cr, version):
    if version == "broken":
        raise ValueError("broken")
    return (cr, version)


class TestTimed(unittest.TestCase):
    def test_passes_the_call_through(self):
        self.assertEqual(timed(migrate)("cr", "19.0"), ("cr", "19.0"))

    def test_keeps_the_signature_odoo_checks(self):
        # exec_script refuses a migrate whose parameters are not (cr, version)
        self.assertEqual(list(inspect.signature(timed(migrate)).parameters), ["cr", "version"])

    def test_logs_the_script_and_how_long_it_took(self):
        with self.assertLogs("oba.timing", "INFO") as logs:
            timed(migrate)("cr", "19.0")
        self.assertRegex(logs.output[0], r"lib/oba/tests/test_timing\.py took \d+\.\d\ds$")

    def test_a_failing_script_is_logged_and_still_raises(self):
        with self.assertLogs("oba.timing", "INFO") as logs, self.assertRaises(ValueError):
            timed(migrate)("cr", "broken")
        self.assertIn("test_timing.py took", logs.output[0])


class TestEveryScriptIsTimed(unittest.TestCase):
    def test_every_migrate_is_decorated_with_timed(self):
        files = [f for pattern in PATTERNS for f in sorted(glob.glob(os.path.join(REPO, pattern)))]
        self.assertTrue(files, "no scripts found")
        bad = []
        for path in files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            migrate_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "migrate"]
            decorated = any(isinstance(d, ast.Name) and d.id == "timed" for n in migrate_defs for d in n.decorator_list)
            if not decorated:
                bad.append(os.path.relpath(path, REPO))
        self.assertEqual(bad, [], "migrate without @timed:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
