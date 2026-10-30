import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-220-fix_mail_templates.py, on the other side of the upgrade.
BACKUP_TABLE = "mail_template_customer_bu"
# Upgrades to 19 still run the upgrade line 1211; same floor as the consumer.
FIRST_TARGET_VERSION = 20
# OdooBot and admin: a template whose last change is theirs was not customized by the customer.
SYSTEM_UIDS = (1, 2)


def migrate(cr, version):
    """Back up the mail templates the customer changed, before the database is sent to Odoo.

    The upgrade can put a customized template back to the standard of the new version. The
    upgrade line it replaces read the old database to bring that content back.

    The whole ``body_html``, with every language, and its ``write_date``: the consumer
    restores only the templates whose ``write_date`` the upgrade changed.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line, on the last request only.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["mail"], position="last"):
        return

    count = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, write_date, body_html
          FROM mail_template
         WHERE write_date IS NOT NULL
           AND body_html IS NOT NULL
           AND COALESCE(write_uid, create_uid) NOT IN %s
        """,
        (SYSTEM_UIDS,),
    )
    _logger.info("Backed up %s mail templates changed by the customer into %s", count, BACKUP_TABLE)
