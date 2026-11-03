import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Up to 19 the user form could add unrestricted cashboxes to "Allowed Cashbox". In 20 the
    # users are set only from a restricted cashbox, and unticking "Restrict Users" clears them:
    # leave unrestricted cashboxes as 20 would, with no users. Anyone with invoicing access
    # still sees and operates them.
    cr.execute(
        """
        DELETE FROM account_cashbox_users_rel rel
         USING account_cashbox cashbox
         WHERE cashbox.id = rel.cashbox_id
           AND cashbox.restrict_users IS NOT TRUE
        """
    )
    _logger.info("Removed %s allowed users from unrestricted cashboxes", cr.rowcount)
