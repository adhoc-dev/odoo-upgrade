import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Tablas de l10n_ar_stock que desaparecen con el pase a Remito digital y que el
# post-upgrade necesita para reconstruir los datos.
BACKUP_TABLES = ["stock_book", "stock_picking_voucher"]

# (tabla, columna) cuyo valor hay que preservar antes del -u.
BACKUP_COLUMNS = [
    ("stock_picking", "book_id"),
    ("stock_picking_type", "book_id"),
]

BACKUP_PREFIX = "_upgrade_"


def migrate(cr, version):
    """Backup de Preimpreso/autoimpresor antes del pase a Remito digital (REM19).

    Migrado desde la upgrade line 2211 ("[REM19] Pre-Adhoc-Ajustes de
    Preimpreso/autoimpresor a Remito digital"), que hacía lo mismo por RPC.

    Los nombres de las copias (`_upgrade_<tabla>` / `_upgrade_book_id`) los
    consumen tal cual las upgrade lines de post (2212) y test (2219), así que no
    se renombran a la convención `_bu` del repo.

    Es idempotente, y la copia se hace una sola vez: si ya está, la corrida nueva no la
    toca. Un `-u` que falla se retoma sobre la misma base, donde los datos vigentes ya
    pueden ser los que migró el intento anterior; rehacer la copia desde ahí se lleva
    puesto el respaldo que el post necesita. En un reintento desde cero la base se
    regenera entera y la copia no existe, así que se hace igual.
    """
    _logger.info("Running 'l10n_ar_stock_remito_digital_backup.py' script for version %s", version)

    for table in BACKUP_TABLES:
        if not util.table_exists(cr, table):
            _logger.info("Table %s does not exist, nothing to back up", table)
            continue
        backup_table = BACKUP_PREFIX + table
        if util.table_exists(cr, backup_table):
            _logger.info("Table %s is already backed up in %s, leaving it", table, backup_table)
            continue
        cr.execute(
            SQL(
                "CREATE TABLE %s AS SELECT * FROM %s",
                SQL.identifier(backup_table),
                SQL.identifier(table),
            )
        )

    for table, column in BACKUP_COLUMNS:
        if not util.column_exists(cr, table, column):
            _logger.info("Column %s.%s does not exist, nothing to back up", table, column)
            continue
        backup_column = BACKUP_PREFIX + column
        if util.column_exists(cr, table, backup_column):
            _logger.info("Column %s.%s is already backed up, leaving it", table, column)
            continue
        util.create_column(cr, table, backup_column, "int4")
        cr.execute(
            SQL(
                "UPDATE %s SET %s = %s",
                SQL.identifier(table),
                SQL.identifier(backup_column),
                SQL.identifier(column),
            )
        )
