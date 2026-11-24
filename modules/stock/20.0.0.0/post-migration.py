import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/190_200/030-backup_stock_picking_batch_installed.py, del otro
# lado del pase.
BACKUP_TABLE = "stock_picking_batch_installed_bu"


def migrate(cr, version):
    """Activa los lotes de traslados en las bases que tenían stock_picking_batch en 19.

    En 19 el menú de Lotes lo ve cualquier usuario de Inventario con el módulo instalado.
    En 20 el módulo vive dentro de `stock` y el menú pide `stock.group_stock_picking_batch`,
    que se activa con la opción de Ajustes. Esto hace lo mismo que tildarla: el grupo pasa a
    ser implícito de los usuarios internos. Si el pase ya lo activó, no cambia nada.
    """
    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: stock_picking_batch was not installed, or the pre-odoo did not run", BACKUP_TABLE)
        return

    env = util.env(cr)
    batch_group = env.ref("stock.group_stock_picking_batch")
    user_group = env.ref("base.group_user")
    if batch_group in user_group.all_implied_ids:
        _logger.info("Batch transfers already enabled for internal users")
        return

    _logger.info("Enabling batch transfers for internal users")
    user_group._apply_group(batch_group)
