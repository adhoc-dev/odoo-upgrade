import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import timed

_logger = logging.getLogger(__name__)

# account_tax_settlement defined these two on account.move.line in 18; in 19 no module does.
_COLUMNS = ("tax_settlement_move_id", "tax_state")


@timed
def migrate(cr, version):
    """Keep tax_settlement_move_id and tax_state as <column>_bu without rewriting account_move_line.

    Renaming only touches the catalog. Copying the columns (UPDATE ... SET x_bu = x) rewrites
    every row of the biggest table of the database and can fill the disk of the pass.
    """
    for column in _COLUMNS:
        backup = f"{column}_bu"
        if not util.column_exists(cr, "account_move_line", column):
            continue
        if util.column_exists(cr, "account_move_line", backup):
            _logger.info("account_move_line.%s already exists: %s not renamed", backup, column)
            continue
        _logger.info("Renaming account_move_line.%s to %s", column, backup)
        cr.execute(
            SQL(
                "ALTER TABLE account_move_line RENAME COLUMN %s TO %s",
                SQL.identifier(column),
                SQL.identifier(backup),
            )
        )
