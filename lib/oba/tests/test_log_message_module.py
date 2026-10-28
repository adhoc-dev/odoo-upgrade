"""Every ``log_message`` call in the scripts that run on every jump names its module.

The provider gets the product of a warning from ``module``. Needs no database:

    /home/odoo/venv/bin/python lib/oba/tests/test_log_message_module.py
"""

import ast
import glob
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PATTERNS = ("modules/base/0.0.0/*.py", "scripts/pre_odoo/always/*.py")


def _is_log_message(node):
    func = node.func
    return isinstance(func, ast.Name) and func.id == "log_message" or (
        isinstance(func, ast.Attribute) and func.attr == "log_message"
    )


class TestLogMessageModule(unittest.TestCase):
    def test_every_call_has_a_literal_module(self):
        files = [f for pattern in PATTERNS for f in sorted(glob.glob(os.path.join(REPO, pattern)))]
        self.assertTrue(files, "no scripts found")
        bad = []
        for path in files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and _is_log_message(node)):
                    continue
                ok = any(
                    kw.arg == "module"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                    and kw.value.value
                    for kw in node.keywords
                )
                if not ok:
                    bad.append("%s:%s" % (os.path.relpath(path, REPO), node.lineno))
        self.assertEqual(bad, [], "log_message without module=<literal>:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
