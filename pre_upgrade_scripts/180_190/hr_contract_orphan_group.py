import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# En 18.0 hr_contract declara dos grupos. El upgrade renombra al módulo hr el xmlid del
# grupo de empleados y borra el del grupo "Administrador" conservando el registro, así que
# el grupo llega vivo y sin xmlid, y el contador de personalizaciones lo factura como una
# customización del cliente.
#
# En la base actualizada no queda nada que lo identifique: el ACL que hr_contract le daba
# solo a él llega renombrado a hr y apuntando al gemelo, porque lo reapunta la plataforma
# antes de que este script corra. Por eso el dato viaja desde la base de origen.
BACKUP_TABLE = "res_groups_xmlid_bu"  # la crea pre_odoo_scripts/180_190/040-backup_group_xmlids.py
GHOST_MODULE, GHOST_NAME = "hr_contract", "group_hr_contract_manager"
# hr_contract lo fusiona la plataforma dentro de hr, así que el xmlid se restaura ahí.
TARGET_MODULE = "hr"


def migrate(cr, version):
    _logger.info("Running 'hr_contract_orphan_group' script for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.warning(
            "No existe la tabla %s: no se reparó ningún grupo. O no corrió el script "
            "pre-odoo, o es una corrida retomada del -u que ya la consumió.",
            BACKUP_TABLE,
        )
        return

    cr.execute(
        SQL(
            """
            SELECT bu.group_id, bu.module, bu.name, g.create_date = bu.create_date
              FROM %s bu
              JOIN res_groups g ON g.id = bu.group_id
             WHERE NOT EXISTS (SELECT 1
                                 FROM ir_model_data d
                                WHERE d.model = 'res.groups'
                                  AND d.res_id = bu.group_id)
          ORDER BY bu.group_id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    for group_id, module, name, same_row in cr.fetchall():
        if (module, name) != (GHOST_MODULE, GHOST_NAME):
            # Cualquier grupo sin xmlid se factura igual: logueralo para que el próximo
            # módulo que Odoo fusione no pase desapercibido.
            _logger.warning("El upgrade dejó sin xmlid al grupo %s (%s.%s)", group_id, module, name)
        elif not same_row:
            # Nunca escribir ante la duda: reparar un id reciclado tapa una personalización real.
            _logger.warning("El grupo %s no es la fila que tenía %s.%s en la base de origen", group_id, module, name)
        else:
            cr.execute(
                SQL(
                    """
                    INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                               create_date, write_date, create_uid, write_uid)
                         VALUES (%s, %s, 'res.groups', %s, true, now(), now(), 1, 1)
                    ON CONFLICT DO NOTHING
                    """,
                    TARGET_MODULE,
                    GHOST_NAME,
                    group_id,
                )
            )
            if cr.rowcount:
                _logger.info("Restaurado el xmlid %s.%s del grupo %s", TARGET_MODULE, GHOST_NAME, group_id)
            else:
                _logger.warning(
                    "El xmlid %s.%s ya está tomado: el grupo %s queda sin reparar",
                    TARGET_MODULE,
                    GHOST_NAME,
                    group_id,
                )

    cr.execute(SQL("DROP TABLE %s", SQL.identifier(BACKUP_TABLE)))
