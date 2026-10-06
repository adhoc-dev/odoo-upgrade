import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/stock/19.0.0.0/end-migration.py, del otro lado del pase.
BACKUP_TABLE = "stock_move_packaging_bu"
# El único salto que deja el empaque en el camino. La carpeta 180_190 ya lo acota; el rango
# se declara igual para que el gate tenga la misma forma que en el resto de los pre-odoo.
TARGET_VERSION = 19


def migrate(cr, version):
    """Respalda el empaque de cada movimiento antes de que el pase borre product.packaging.

    En 19 el empaque dejó de ser un modelo propio y pasó a ser una UdM del producto
    (product.template.uom_ids). El pase crea esas UdM pero no baja el dato a los
    movimientos: `stock_move.packaging_uom_id` queda en la UdM del producto y el remito
    pierde el empaque (en haulani, 47.931 de 48.254 movimientos de salida).

    Se respalda el nombre y la cantidad del empaque, no su id: del otro lado del pase la
    tabla product_packaging ya no existe, así que el id no sirve para nada. El producto que
    se guarda es el del empaque, que es donde el pase crea la UdM, no el del movimiento
    (coinciden salvo dato inconsistente).

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    # Borra BACKUP_TABLE primero, así una tabla de una corrida anterior no viaja en un
    # request al que el script no aplica. El gate de módulo va acá porque el pre-odoo corre
    # sobre toda la base, sin filtrar por módulo.
    if not should_back_up(
        cr, BACKUP_TABLE, first_target=TARGET_VERSION, last_target=TARGET_VERSION, modules=["stock"]
    ):
        return

    _logger.info("Respaldando el empaque de los movimientos en %s", BACKUP_TABLE)
    backed_up = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT m.id, p.product_id, p.name AS packaging_name, p.qty AS packaging_qty
          FROM stock_move m
          JOIN product_packaging p ON p.id = m.product_packaging_id
        """,
    )
    _logger.info("Se respaldaron %s movimientos con empaque", backed_up)
