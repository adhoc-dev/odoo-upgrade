import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-060-check_credit_card_journals.py, on the other side of the upgrade.
BACKUP_TABLE = "account_journal_credit_card_bu"
# Upgrades to 19 still run the upgrade line; same floor as the consumer.
FIRST_TARGET_VERSION = 20
CREDIT_CARD_CODES = ("inbound_credit_card", "outbound_credit_card")


def migrate(cr, version):
    """Back up the type of the credit card journals before the database is sent to Odoo.

    Before 16.0 a journal was made a credit card one through its payment methods, and the
    upgrade can change its type. The upgrade line it replaces read them from the old database to warn about the ones that changed.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["account"]):
        return

    _logger.info("Backing up the type of the credit card journals into %s", BACKUP_TABLE)
    create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT DISTINCT j.id, j.type
          FROM account_journal j
          JOIN account_payment_method_line l ON l.journal_id = j.id
          JOIN account_payment_method m ON m.id = l.payment_method_id
         WHERE j.active
           AND m.code IN %s
        """,
        (CREDIT_CARD_CODES,),
    )
