import logging

from odoo.release import major_version
from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe oba/customer_note.py, desde los scripts de migración de este mismo upgrade.
TABLE = "oba_upgrade_customer_note"


def migrate(cr, version):
    """Borra los valores de customer notes que dejó el salto anterior.

    La tabla viaja a la base nueva con las filas del salto anterior, y el guard del helper
    identifica a cada script por su path, así que sin esto una carpeta de versión que se
    mueve aborta el upgrade siguiente.

    Se borran solo las filas de otras versiones: las de este salto las escriben los scripts
    de los módulos que el `-u` ya pasó, y en una corrida retomada esos módulos no vuelven a
    correr. Borrarlas todas al arrancar perdía sus notas sin que nada avisara.

    Ojo si el helper llega a aceptar callers de `pre_odoo_scripts/`: esas filas se escriben
    antes del viaje y esto las destruiría.
    """
    _logger.info("Running 'clear_previous_customer_notes.py' script for version %s", version)

    if not util.table_exists(cr, TABLE):
        return

    # `script` es "<módulo>/<versión>/<archivo>.py", y la carpeta de versión de un script que
    # corre en este upgrade arranca con la major a la que estamos yendo. El `VERSION_RE` del
    # helper también acepta carpetas con la versión pelada del módulo (`1.0`), que no dicen a
    # qué salto pertenecen: esas se dejan y se avisan, antes que perder una nota en silencio.
    # Se reconoce una major de Odoo por sus dos dígitos — las de este repo van de la 15 para
    # arriba.
    version_of_script = SQL("split_part(script, '/', 2)")
    has_odoo_major = SQL("%s ~ '^[0-9][0-9]+\\.'", version_of_script)

    cr.execute(SQL("SELECT slug, script FROM %s WHERE NOT %s", SQL.identifier(TABLE), has_odoo_major))
    for slug, script in cr.fetchall():
        _logger.warning(
            "La nota %r la escribió %s, cuya carpeta de versión no dice a qué salto pertenece: se deja como está",
            slug,
            script,
        )

    cr.execute(
        SQL(
            "DELETE FROM %s WHERE %s AND %s NOT LIKE %s",
            SQL.identifier(TABLE),
            has_odoo_major,
            version_of_script,
            "%s.%%" % major_version.split(".")[0],
        )
    )
    _logger.info("Cleared %s customer note value(s) left by the previous upgrade", cr.rowcount)
