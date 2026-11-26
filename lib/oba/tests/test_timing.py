"""``timed`` logs how long a script took.

Needs no database nor Odoo:

    PYTHONPATH=lib python3 lib/oba/tests/test_timing.py
"""

import inspect
import unittest

from oba import timed


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


if __name__ == "__main__":
    unittest.main()
