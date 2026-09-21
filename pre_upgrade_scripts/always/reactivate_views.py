import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La crea pre_odoo_scripts/always/010-backup_active_views.py sobre la base vieja.
BACKUP_TABLE = "ir_ui_view_active_bu"


def migrate(cr, version):
    """Re-activa las vistas que Odoo desactivó durante su upgrade.

    Migrado desde la upgrade line 507 ("Re-activar vistas"), que leía las vistas
    activas de la base old por RPC. Odoo desactiva las que le dan error; las
    volvemos a activar porque es probable que nuestro `-u` las arregle, y al final
    del upgrade igual chequeamos las que quedan rotas y las reportamos.

    Se hace por SQL para no disparar el `_validate_fields` que corre al escribir
    `active` por ORM: si la vista todavía está rota, el write fallaría.

    Cada vista se re-activa una sola vez, la primera: el respaldo se consume acá. Las
    que desactiva nuestro propio `-u` no entran en el juego —las rotas las reporta el
    chequeo del final, y algunas las apagan nuestros módulos a propósito por data, como
    `stock_ux` con `stock.product_search_form_view_stock`—, así que una corrida retomada
    no las tiene que resucitar: sin la tabla, no hace nada.
    """
    _logger.info("Running 'reactivate_views.py' script for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.warning(
            "No existe la tabla %s: no se re-activó ninguna vista. O no corrió el script "
            "pre-odoo, o es una corrida retomada del -u que ya la consumió.",
            BACKUP_TABLE,
        )
        return

    cr.execute(
        SQL(
            """
            UPDATE ir_ui_view view
               SET active = true
              FROM %s backup
             WHERE view.id = backup.id
               AND NOT view.active
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    _logger.info("Re-activated %s views disabled during the Odoo upgrade", cr.rowcount)

    cr.execute(SQL("DROP TABLE %s", SQL.identifier(BACKUP_TABLE)))
