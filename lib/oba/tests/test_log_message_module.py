"""Every ``log_message`` call in the scripts that run on every jump is a warning or an error that names its module.

The provider gets the product of a warning from ``module``. An ``info`` goes to ``_logger.info``,
which ends in the process log. Needs no database:

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
    def test_every_call_has_a_type_and_a_literal_module(self):
        files = [f for pattern in PATTERNS for f in sorted(glob.glob(os.path.join(REPO, pattern)))]
        self.assertTrue(files, "no scripts found")
        bad = []
        for path in files:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and _is_log_message(node)):
                    continue
                kwargs = {kw.arg: kw.value for kw in node.keywords}
                type_ = kwargs.get("type", node.args[2] if len(node.args) > 2 else None)
                module = kwargs.get("module")
                where = "%s:%s" % (os.path.relpath(path, REPO), node.lineno)
                if not (isinstance(type_, ast.Constant) and type_.value in ("warning", "error")):
                    bad.append("%s: an info goes to _logger.info" % where)
                elif not (isinstance(module, ast.Constant) and isinstance(module.value, str) and module.value):
                    bad.append("%s: without module=<literal>" % where)
        self.assertEqual(bad, [], "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
