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
followup_levels = _load_script("030-backup_followup_levels.py")


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

    def test_nothing_without_account_reports(self):
        residual_column.migrate(self.cr, "19.0")
        self.assertEqual(self.columns(), [1, 2, 3, 4, 5])

    def test_nothing_on_an_upgrade_to_19(self):
        self.install("account_reports")
        self.write_context(from_version="18.0", to_version="19.0")
        residual_column.migrate(self.cr, "18.0")
        self.assertEqual(self.columns(), [1, 2, 3, 4, 5])


class TestBackupFollowupLevels(OldDatabaseCase):
    TABLES = """
        CREATE TABLE res_partner (id integer PRIMARY KEY, lang varchar);
        CREATE TABLE res_company (id integer PRIMARY KEY, partner_id integer);
        CREATE TABLE account_followup_followup_line (
            id integer PRIMARY KEY, company_id integer, name jsonb, delay integer,
            auto_execute boolean, send_email boolean, send_sms boolean, create_activity boolean,
            mail_template_id integer, sms_template_id integer, join_invoices boolean
        );
        CREATE TABLE account_followup_followup_line_res_users_rel (
            account_followup_followup_line_id integer, res_users_id integer
        );
        CREATE TABLE account_move_line (id serial PRIMARY KEY, followup_line_id integer, date date);
    """

    def setUp(self):
        super().setUp()
        self.cr.execute(
            """
            INSERT INTO res_partner VALUES (1, 'es_AR'), (2, NULL);
            INSERT INTO res_company VALUES (1, 1), (2, 2);
            INSERT INTO account_followup_followup_line VALUES
                (1, 1, '{"en_US": "First", "es_AR": "Primero"}', 15, true, true, false, false, 7, NULL, true),
                (2, 1, '{"en_US": "Second"}', 30, false, true, true, true, 8, 9, false),
                (3, 2, '{"fr_FR": "Troisième"}', 10, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
            INSERT INTO account_followup_followup_line_res_users_rel VALUES (2, 5), (2, 6);
            INSERT INTO account_move_line (followup_line_id, date) VALUES
                (1, CURRENT_DATE - 10), (2, CURRENT_DATE - 200), (NULL, CURRENT_DATE);
            """
        )

    def backup(self):
        return self.rows(
            """
            SELECT id, company_id, name, delay, auto_execute, send_email, send_sms, create_activity,
                   mail_template_id, sms_template_id, join_invoices, followers, used
              FROM account_followup_followup_line_bu ORDER BY id
            """
        )

    def test_backs_up_what_20_drops_and_whether_each_level_was_used(self):
        self.install("account_followup")
        self.write_context()
        followup_levels.migrate(self.cr, "19.0")
        self.assertEqual(
            self.backup(),
            [
                # The name in the language of the company, used in the last 180 days.
                (1, 1, "Primero", 15, True, True, False, False, 7, None, True, 0, True),
                # No translation in that language: English. Used 200 days ago: not used.
                (2, 1, "Second", 30, False, True, True, True, 8, 9, False, 2, False),
                # No language and no English: whatever it has. NULL booleans as false.
                (3, 2, "Troisième", 10, False, False, False, False, None, None, False, 0, False),
            ],
        )

    def test_second_run_backs_up_the_same(self):
        self.install("account_followup")
        followup_levels.migrate(self.cr, "19.0")
        first = self.backup()
        followup_levels.migrate(self.cr, "19.0")
        self.assertEqual(self.backup(), first)

    def test_without_the_followers_table(self):
        self.cr.execute("DROP TABLE account_followup_followup_line_res_users_rel")
        self.install("account_followup")
        followup_levels.migrate(self.cr, "19.0")
        self.assertEqual([row[11] for row in self.backup()], [0, 0, 0])

    def test_drops_an_old_backup_without_account_followup(self):
        self.install("account_followup")
        followup_levels.migrate(self.cr, "19.0")
        self.cr.execute("DELETE FROM ir_module_module")
        followup_levels.migrate(self.cr, "19.0")
        self.assertEqual(self.rows("SELECT to_regclass('account_followup_followup_line_bu')"), [(None,)])

    def test_nothing_on_an_upgrade_to_19(self):
        self.install("account_followup")
        self.write_context(from_version="18.0", to_version="19.0")
        followup_levels.migrate(self.cr, "18.0")
        self.assertEqual(self.rows("SELECT to_regclass('account_followup_followup_line_bu')"), [(None,)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
