import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/stock/20.0.0.0/post-migration.py, del otro lado del pase.
BACKUP_TABLE = "stock_picking_batch_installed_bu"
TARGET_VERSION = 20


def migrate(cr, version):
    """Deja anotado que la base tenía stock_picking_batch instalado.

    En 20 el módulo se fusiona en `stock`: después del pase ya no figura en
    ir_module_module, y del otro lado no hay forma de saber si la base lo usaba.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    if not should_back_up(
        cr, BACKUP_TABLE, first_target=TARGET_VERSION, last_target=TARGET_VERSION, modules=["stock_picking_batch"]
    ):
        return

    _logger.info("stock_picking_batch is installed: noting it in %s", BACKUP_TABLE)
    create_backup(
        cr,
        BACKUP_TABLE,
        "SELECT id FROM ir_module_module WHERE name = 'stock_picking_batch'",
    )
