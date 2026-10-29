import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message, request_context

_logger = logging.getLogger(__name__)

# Backed up by scripts/pre_odoo/190_200/020-backup_res_bank.py.
BANK_TABLE = "res_bank_bu"


def migrate(cr, version):
    """Warn when the database had banks and nothing installed base_bank to restore them."""
    if not util.table_exists(cr, BANK_TABLE) or util.module_installed(cr, "base_bank"):
        return
    cr.execute(SQL("SELECT count(*) FROM %s", SQL.identifier(BANK_TABLE)))
    count = cr.fetchone()[0]
    if not count:
        return
    message = (
        "%s banks were not restored: Odoo 20 removed them from base and base_bank is not installed. "
        "They are kept in %s." % (count, BANK_TABLE)
    )
    if request_context(cr):
        log_message(cr, message, "warning")
    else:
        _logger.warning(message)
