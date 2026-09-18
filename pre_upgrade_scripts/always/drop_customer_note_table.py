import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe oba/customer_note.py, desde los scripts de migración de este mismo upgrade.
TABLE = "oba_upgrade_customer_note"


def migrate(cr, version):
    """Borra los valores de customer notes: los de este upgrade los escriben sus scripts.

    La tabla viaja a la base nueva con las filas del salto anterior, y el guard del helper
    identifica a cada script por su path, así que sin esto una carpeta de versión que se
    mueve aborta el upgrade siguiente.

    Ojo si el helper llega a aceptar callers de `pre_odoo_scripts/`: esas filas se escriben
    antes del viaje y esto las destruiría.
    """
    _logger.info("Running 'drop_customer_note_table.py' script for version %s", version)

    if not util.table_exists(cr, TABLE):
        return

    cr.execute(SQL("DROP TABLE %s", SQL.identifier(TABLE)))
    _logger.info("Dropped %s: this upgrade's own scripts write the values it publishes", TABLE)
