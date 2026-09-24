"""Warn about the credit card journals whose type changed in the upgrade.

Reads what pre_odoo_scripts/always/060-backup_credit_card_journals.py backed up on the old
database. Only a warning, as the upgrade line: which type is right is decided by hand.

In ``base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "account_journal_credit_card_bu"
# The upgrade line only ran on upgrades to 18.0 and later.
FIRST_TARGET_VERSION = 18


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no credit card journals to check", BACKUP_TABLE)
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    cr.execute(
        SQL(
            """
            SELECT j.id
              FROM %s bu
              JOIN account_journal j ON j.id = bu.id
             WHERE j.type != bu.type
             ORDER BY j.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    journal_ids = [row[0] for row in cr.fetchall()]
    if journal_ids:
        _logger.warning(
            "%s credit card journals changed their type in the upgrade: %s", len(journal_ids), journal_ids
        )
