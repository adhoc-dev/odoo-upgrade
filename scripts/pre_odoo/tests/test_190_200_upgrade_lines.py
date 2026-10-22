"""The scripts of ``scripts/pre_odoo/190_200``, case by case.

Same setup as ``test_always_upgrade_lines.py``: each case builds the tables the script
touches in a Postgres database of its own, so no Odoo runs.

    /home/odoo/venv/bin/python scripts/pre_odoo/tests/test_190_200_upgrade_lines.py
"""

import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_always_upgrade_lines import REPO, OldDatabaseCase  # noqa: E402

SCRIPTS = os.path.join(REPO, "scripts", "pre_odoo", "190_200")


def _load_script(filename):
    """Load a script by path: the folder is not a package and the name starts with a digit."""
    name = "s" + filename[:-3].replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


residual_column = _load_script("020-followup_report_residual_column.py")


class TestFollowupReportResidualColumn(OldDatabaseCase):
    TABLES = """
        CREATE TABLE account_report_column (
            id serial PRIMARY KEY, report_id integer, expression_label varchar
        );
    """
    FOLLOWUP, OTHER = 17, 18

    def setUp(self):
        super().setUp()
        self.xmlid("account_reports", "followup_report", "account.report", self.FOLLOWUP)
        self.xmlid("account_reports", "partner_ledger_report", "account.report", self.OTHER)
        self.cr.execute(
            """
            INSERT INTO account_report_column (id, report_id, expression_label) VALUES
                (1, %(followup)s, 'date'),
                (2, %(followup)s, 'amount_residual'),
                (3, %(other)s, 'amount_residual'),
                (4, %(followup)s, 'invoicing_date'),
                (5, %(followup)s, 'custom_column')
            """,
            {"followup": self.FOLLOWUP, "other": self.OTHER},
        )
        self.xmlid("account_reports", "followup_report_date", "account.report.column", 1)
        self.xmlid("account_reports", "followup_report_invoicing_date", "account.report.column", 4)

    def columns(self):
        return [row[0] for row in self.rows("SELECT id FROM account_report_column ORDER BY id")]

    def test_drops_only_the_residual_column_without_xmlid_of_the_follow_up_report(self):
        self.install("account_reports")
        self.write_context()
        residual_column.migrate(self.cr, "19.0")
        self.assertEqual(self.columns(), [1, 3, 4, 5])
        self.assertEqual(len(self.logs()), 1)

    def test_keeps_a_residual_column_with_xmlid(self):
        self.xmlid("account_reports", "followup_report_amount_residual", "account.report.column", 2)
        self.install("account_reports")
        residual_column.migrate(self.cr, "19.0")
        self.assertEqual(self.columns(), [1, 2, 3, 4, 5])
        self.assertEqual(self.logs(), [])

    def test_second_run_changes_nothing(self):
        self.install("account_reports")
        residual_column.migrate(self.cr, "19.0")
        residual_column.migrate(self.cr, "19.0")
        self.assertEqual(self.columns(), [1, 3, 4, 5])
        self.assertEqual(len(self.logs()), 1)

    def test_nothing_without_account_reports(self):
        residual_column.migrate(self.cr, "19.0")
        self.assertEqual(self.columns(), [1, 2, 3, 4, 5])

    def test_nothing_on_an_upgrade_to_19(self):
        self.install("account_reports")
        self.write_context(from_version="18.0", to_version="19.0")
        residual_column.migrate(self.cr, "18.0")
        self.assertEqual(self.columns(), [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main(verbosity=2)
