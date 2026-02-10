import logging

from odoo.tools import sql
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

_table_renames = [
    ("stock_book", "stock_book_bu"),]


def migrate(cr, version):
    _logger.debug('Running migrate script for l10n_ar_stock')

    # backup de stock_book
    for old_table, new_table in _table_renames:
        if sql.table_exists(cr, old_table) and not sql.table_exists(cr, new_table):
            _logger.info("Creando backup de %s como %s", old_table, new_table)
            util.rename_table(cr, old_table, new_table)
