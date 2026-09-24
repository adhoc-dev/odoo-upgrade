import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-check_credit_card_journals.py, on the other side of the upgrade.
BACKUP_TABLE = "account_journal_credit_card_bu"
CREDIT_CARD_CODES = ("inbound_credit_card", "outbound_credit_card")


def migrate(cr, version):
    """Back up the type of the credit card journals before the database is sent to Odoo.

    Before 16.0 a journal was made a credit card one through its payment methods, and the
    upgrade can change its type. The upgrade line it replaces read them from the old database to warn about the ones that changed.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Only with account installed, like the upgrade line; the version gate is in the consumer.
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'account' AND state = 'installed'")
    if not cr.fetchone():
        return

    _logger.info("Backing up the type of the credit card journals into %s", BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT DISTINCT j.id, j.type
              FROM account_journal j
              JOIN account_payment_method_line l ON l.journal_id = j.id
              JOIN account_payment_method m ON m.id = l.payment_method_id
             WHERE j.active
               AND m.code IN %%s
        """
        % BACKUP_TABLE,
        (CREDIT_CARD_CODES,),
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
