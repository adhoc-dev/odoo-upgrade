"""The backup of the SII send cron of ``scripts/pre_odoo/190_200/020-l10n_cl_edi_send_dte_cron.py``.

Same harness as ``test_always_upgrade_lines``: an own Postgres database, no Odoo running.

    /home/odoo/venv/bin/python scripts/pre_odoo/tests/test_l10n_cl_edi_send_dte_cron.py
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(REPO, "scripts", "pre_odoo", "190_200", "020-l10n_cl_edi_send_dte_cron.py")

sys.path.insert(0, HERE)

from test_always_upgrade_lines import OldDatabaseCase  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location("s020_l10n_cl_edi_send_dte_cron", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cron_backup = _load_script()
TABLE = cron_backup.BACKUP_TABLE


class TestSendDteCronBackup(OldDatabaseCase):
    TABLES = """
        CREATE TABLE ir_cron (
            id serial PRIMARY KEY, active boolean, interval_number integer,
            interval_type varchar, nextcall timestamp
        );
    """
    CRON = 7

    def setUp(self):
        super().setUp()
        self.install("saas_client_l10n_cl")
        self.xmlid("l10n_cl_edi", "ir_cron_send_send", "ir.cron", self.CRON)
        # Another changed cron: only the one of l10n_cl_edi is backed up.
        self.cron(8, True, 4, "hours")

    def cron(self, cron_id, active, interval_number, interval_type):
        self.cr.execute(
            "INSERT INTO ir_cron (id, active, interval_number, interval_type, nextcall) "
            "VALUES (%s, %s, %s, %s, '2026-11-02 22:00:00')",
            (cron_id, active, interval_number, interval_type),
        )

    def backup(self):
        return self.rows("SELECT id, active, interval_number, interval_type FROM %s" % TABLE)

    def test_backs_up_a_changed_interval(self):
        self.cron(self.CRON, True, 4, "hours")
        cron_backup.migrate(self.cr, "19.0")
        self.assertEqual(self.backup(), [(self.CRON, True, 4, "hours")])

    def test_backs_up_an_inactive_cron(self):
        self.cron(self.CRON, False, 1, "days")
        cron_backup.migrate(self.cr, "19.0")
        self.assertEqual(self.backup(), [(self.CRON, False, 1, "days")])

    def test_skips_the_default_of_19(self):
        self.cron(self.CRON, True, 1, "days")
        cron_backup.migrate(self.cr, "19.0")
        self.assertEqual(self.backup(), [])

    def test_skips_without_the_module(self):
        self.cron(self.CRON, True, 4, "hours")
        self.cr.execute("DELETE FROM ir_module_module")
        cron_backup.migrate(self.cr, "19.0")
        self.assertFalse(self.rows("SELECT 1 FROM pg_tables WHERE tablename = %s", (TABLE,)))

    def test_skips_another_target(self):
        self.cron(self.CRON, True, 4, "hours")
        self.write_context(from_version="18.0", to_version="19.0")
        cron_backup.migrate(self.cr, "18.0")
        self.assertFalse(self.rows("SELECT 1 FROM pg_tables WHERE tablename = %s", (TABLE,)))

    def test_second_run_replaces_the_backup(self):
        self.cron(self.CRON, True, 4, "hours")
        cron_backup.migrate(self.cr, "19.0")
        self.cr.execute("UPDATE ir_cron SET interval_number = 1, interval_type = 'days' WHERE id = %s", (self.CRON,))
        cron_backup.migrate(self.cr, "19.0")
        self.assertEqual(self.backup(), [])


if __name__ == "__main__":
    unittest.main()
