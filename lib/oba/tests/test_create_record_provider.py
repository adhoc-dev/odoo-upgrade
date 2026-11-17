"""White-box tests for the checks of ``create_record_provider``: a malformed call fails before
touching the database. What a good call leaves is in ``test_request_channel.py``.

They need neither Postgres nor Odoo:

    python3 lib/oba/tests/test_create_record_provider.py
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from oba import create_record_provider  # noqa: E402


class TestCreateRecordProvider(unittest.TestCase):
    def setUp(self):
        self.cr = mock.Mock()

    def test_a_malformed_call_fails_before_touching_the_database(self):
        cases = [
            ("", {"name": "x"}, {}),
            (None, {"name": "x"}, {}),
            (["project.task"], {"name": "x"}, {}),
            ("project.task", {}, {}),
            ("project.task", [("name", "x")], {}),
            ("project.task", {1: "x"}, {}),
            ("project.task", {"name": "x"}, {"context": ["a"]}),
            ("project.task", {"name": "x"}, {"context": {1: "x"}}),
            ("project.task", {"name": "x"}, {"ref": ""}),
            ("project.task", {"name": "x"}, {"ref": 12}),
            ("project.task", {"name": object()}, {}),
            ("project.task", {"amount": float("nan")}, {}),
            ("project.task", {"name": "a\x00b"}, {}),
            ("project.task", {"parent_id": {"$request": "other_ticket"}}, {}),
            ("project.task", {"parent_id": {"$request": ["upgrade_ticket"]}}, {}),
        ]
        for model, vals, kwargs in cases:
            with self.subTest(model=model, vals=vals, kwargs=kwargs), self.assertRaises(ValueError):
                create_record_provider(self.cr, model, vals, **kwargs)
        self.cr.execute.assert_not_called()

    def test_context_and_ref_go_by_keyword(self):
        with self.assertRaises(TypeError):
            create_record_provider(self.cr, "project.task", {"name": "x"}, {}, "ref")


if __name__ == "__main__":
    unittest.main()
