import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# The post-migration of this folder reads it, on the other side of the module update.
BACKUP_COLUMN = "previous_value_bu"


def migrate(cr, version):
    """Keep the value in force before each adjustment.

    In 19 the module stored it in ``product_value.previous_value``. Odoo 20 keeps it in
    ``old_value`` / ``old_cost`` and the module no longer has that field, so its column is
    dropped when the module is updated.
    """
    if not util.column_exists(cr, "product_value", "previous_value"):
        _logger.info("product_value.previous_value does not exist: nothing to keep")
        return
    util.create_column(cr, "product_value", BACKUP_COLUMN, "numeric")
    cr.execute(
        SQL(
            "UPDATE product_value SET %(backup)s = previous_value WHERE previous_value IS NOT NULL",
            backup=SQL.identifier(BACKUP_COLUMN),
        )
    )
    _logger.info("Kept previous_value of %s value adjustments in %s", cr.rowcount, BACKUP_COLUMN)
