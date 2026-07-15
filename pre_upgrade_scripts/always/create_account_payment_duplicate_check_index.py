import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'create_account_payment_duplicate_check_index.py' script for version %s", version)
    if not util.table_exists(cr, "account_payment"):
        return
    cr.execute(
        SQL(
            """
            CREATE INDEX IF NOT EXISTS account_payment_duplicate_check_idx
                ON account_payment (partner_id, company_id, date, payment_type, amount)
             WHERE state IN ('draft', 'in_process')
            """
        )
    )
