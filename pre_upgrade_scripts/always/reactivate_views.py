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
    """
    _logger.info("Running 'reactivate_views.py' script for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.warning(
            "No existe la tabla %s: no se sabe qué vistas estaban activas antes del "
            "upgrade y no se re-activó ninguna. Revisar que el script pre-odoo haya corrido.",
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
