import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-220-account_groups_to_parent_accounts.py, on the other side of the upgrade.
BACKUP_TABLE = "account_group_bu"
# 20 is the version that drops account.group.
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the account groups before the database is sent to Odoo.

    20 drops ``account.group`` and its charts ship the groups as archived parent accounts.
    The groups and their xmlids are kept here so that the other side can build those parent
    accounts if the upgrade does not.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=["account"]):
        return

    _logger.info("Backing up the account groups into %s", BACKUP_TABLE)
    count = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT g.id, g.company_id, g.parent_id, g.name, g.code_prefix_start, g.code_prefix_end,
               d.module AS xmlid_module, d.name AS xmlid_name
          FROM account_group g
          LEFT JOIN LATERAL (
                SELECT module, name
                  FROM ir_model_data
                 WHERE model = 'account.group'
                   AND res_id = g.id
                 ORDER BY id
                 LIMIT 1
          ) d ON TRUE
         WHERE g.code_prefix_start IS NOT NULL
        """,
    )
    _logger.info("%s account groups backed up", count)
