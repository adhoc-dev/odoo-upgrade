import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Las crea pre_odoo_scripts/180_190/040-backup_customization_xmlids.py sobre la base vieja.
XMLID_TABLE = "ir_model_data_personalizacion_bu"
EXISTING_TABLE = "registros_contados_bu"

# Tabla de cada modelo que el contador mira, para poder chequear que el registro sigue vivo.
TABLE_BY_MODEL = {
    "ir.model": "ir_model",
    "ir.model.fields": "ir_model_fields",
    "ir.ui.view": "ir_ui_view",
    "ir.actions.server": "ir_act_server",
    "ir.cron": "ir_cron",
    "ir.actions.report": "ir_act_report_xml",
    "res.groups": "res_groups",
    "ir.rule": "ir_rule",
    "ir.model.access": "ir_model_access",
    "base.automation": "base_automation",
}

# Modulos que desaparecieron en el pase y el modulo que los absorbio. Se completa a mano, con
# lo que reporte el log de este mismo script: no hay forma de deducir el sucesor, y reponer el
# XML ID apuntando a un modulo que ya no existe deja basura que el proximo upgrade vuelve a
# borrar. Mismo criterio que MERGE_MODULES en merge_and_renames.py.
MODULE_SUCCESSORS = {}

# Modulos del backup que NO hay que reponer ni reportar. `verification in progress` no es un
# modulo real: pre_upgrade_scripts/always/delete_verification_in_progress_xmlids.py borra sus
# ir_model_data a proposito, y la carpeta `always` corre antes que esta (el runner arma la lista
# como always + <from>_<to>, ver odoo_obaupgrade.py::_get_pre_upgrade_scripts). Sin esto, cada
# base reportaria esos registros como huerfanos sin sucesor.
IGNORED_MODULES = ("verification in progress",)


def migrate(cr, version):
    """Saca del contador de personalizaciones lo que no es personalizacion del cliente.

    El contador (wizard "Mi base") toma como personalizacion del cliente todo registro sin
    ir_model_data, y despues del pase se cuentan cosas que el cliente no hizo. Son dos casos y
    se atacan distinto, en este orden:

    1. El registro EXISTIA y perdio su XML ID porque Odoo fusiono o elimino su modulo: se le
       repone el XML ID y deja de contarse.
    2. El registro NO EXISTIA antes: no lo hizo el cliente, lo creo la migracion. Se desactiva.

    Primero se repone y despues se desactiva, para que un huerfano identificable no termine
    apagado.

    Los que quedaron con XML ID de `__import__`, `__custom__` o `studio_customization` no se
    tocan en ninguno de los dos pasos: esos cuentan por el cambio de criterio del contador entre
    18 y 19 (en 18 solo contaba `__export__`), que es una decision de producto y no algo que la
    migracion haya roto.
    """
    _logger.info("Running 'fix_counted_customizations.py' script for version %s", version)

    _restore_lost_xmlids(cr)
    _deactivate_records_that_did_not_exist(cr)

    cr.execute(SQL("DROP TABLE IF EXISTS %s", SQL.identifier(XMLID_TABLE)))
    cr.execute(SQL("DROP TABLE IF EXISTS %s", SQL.identifier(EXISTING_TABLE)))


def _restore_lost_xmlids(cr):
    """Repone el XML ID de los registros que lo perdieron en el pase a Odoo.

    Se repone lo que se puede resolver sin adivinar; el resto se reporta para que se declare el
    sucesor en MODULE_SUCCESSORS.
    """
    if not util.table_exists(cr, XMLID_TABLE):
        _logger.warning(
            "No existe la tabla %s: no se sabe que XML ID tenia cada registro antes del pase y "
            "no se repuso ninguno. Revisar que el script pre-odoo haya corrido.",
            XMLID_TABLE,
        )
        return

    restored = 0
    for model, table in TABLE_BY_MODEL.items():
        if not util.table_exists(cr, table):
            continue
        # Se repone solo si: el registro sigue existiendo, hoy no tiene ningun ir_model_data, y
        # el modulo del backup sigue en la base. El ON CONFLICT cubre el caso de que el par
        # (module, name) ya lo ocupe otro registro: ahi no se puede reponer sin pisar.
        cr.execute(
            SQL(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                     SELECT backup.module, backup.name, backup.model, backup.res_id, backup.noupdate
                       FROM %(backup)s backup
                       JOIN %(table)s record ON record.id = backup.res_id
                       JOIN ir_module_module imm ON imm.name = backup.module
                      WHERE backup.model = %(model)s
                        AND backup.module NOT IN %(ignored)s
                        AND NOT EXISTS (
                            SELECT 1 FROM ir_model_data imd
                             WHERE imd.model = backup.model AND imd.res_id = backup.res_id
                        )
                ON CONFLICT (module, name) DO NOTHING
                """,
                backup=SQL.identifier(XMLID_TABLE),
                table=SQL.identifier(table),
                model=model,
                ignored=IGNORED_MODULES,
            )
        )
        if cr.rowcount:
            _logger.info("Restored %s XML IDs for %s", cr.rowcount, model)
            restored += cr.rowcount
    _logger.info("Restored %s customization XML IDs in total", restored)

    # Lo que no se pudo reponer porque el modulo ya no existe: se reporta agrupado para poder
    # declarar el sucesor. No se repone a ciegas.
    cr.execute(
        SQL(
            """
            SELECT backup.module, backup.model, count(*)
              FROM %(backup)s backup
             WHERE backup.module NOT IN %(ignored)s
               AND NOT EXISTS (
                     SELECT 1 FROM ir_module_module imm WHERE imm.name = backup.module
                   )
               AND NOT EXISTS (
                     SELECT 1 FROM ir_model_data imd
                      WHERE imd.model = backup.model AND imd.res_id = backup.res_id
                   )
          GROUP BY backup.module, backup.model
          ORDER BY count(*) DESC
            """,
            backup=SQL.identifier(XMLID_TABLE),
            ignored=IGNORED_MODULES,
        )
    )
    orphans = cr.fetchall()
    for module, model, count in orphans:
        successor = MODULE_SUCCESSORS.get(module)
        if successor:
            # El sucesor lo declaro una persona mirando un reporte previo de este mismo script,
            # asi que aca si se repone: el XML ID pasa a colgar del modulo que absorbio al viejo.
            cr.execute(
                SQL(
                    """
                    INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                         SELECT %(successor)s, backup.name, backup.model, backup.res_id, backup.noupdate
                           FROM %(backup)s backup
                          WHERE backup.module = %(module)s
                            AND backup.model = %(model)s
                            AND NOT EXISTS (
                                SELECT 1 FROM ir_model_data imd
                                 WHERE imd.model = backup.model AND imd.res_id = backup.res_id
                            )
                    ON CONFLICT (module, name) DO NOTHING
                    """,
                    backup=SQL.identifier(XMLID_TABLE),
                    successor=successor,
                    module=module,
                    model=model,
                )
            )
            _logger.info(
                "Module %s is gone: moved %s of %s %s records to %s",
                module,
                cr.rowcount,
                count,
                model,
                successor,
            )
        else:
            _logger.warning(
                "Module %s ya no existe y %s registros de %s quedaron sin XML ID: se van a contar "
                "como personalizacion del cliente. Declarar el sucesor en MODULE_SUCCESSORS.",
                module,
                count,
                model,
            )


def _deactivate_records_that_did_not_exist(cr):
    """Desactiva los registros que se cuentan como personalizacion y no existian antes del pase.

    Si el registro no estaba en la base vieja, no lo hizo el cliente: lo creo la migracion. Se
    desactiva en vez de borrarse, que es reversible y no rompe referencias.

    Corre DESPUES de reponer los XML IDs a proposito: lo que se pudo identificar ya dejo de
    contarse y no llega hasta aca.

    Por que es seguro desactivar aca, y es por la ubicacion: en este punto la base es todavia
    la que devolvio Odoo. Nuestro proceso no creo nada aun -- lo nuestro se crea despues, en el
    `-u` y en las upgrade lines de tipo `4_post` --, asi que todo lo que aparezca contandose sin
    haber existido antes lo creo el pase, no nosotros.

    Esa premisa es una invariante, no una casualidad: si algun dia un script nuestro anterior a
    este empieza a crear registros de estos modelos, este script los va a apagar. Lo que el
    proceso cree para que el cliente lo use tiene que (a) crearse despues de este punto y (b)
    nacer con su XML ID, que es lo que lo saca del contador de una.

    El caso que lo ilustra: la UL 2212 (`4_post`) le borra al cliente el remito aeroo y le deja
    en su lugar un reporte nuevo que el cliente SI usa. Ese reporte tampoco existia antes del
    pase, y apagarlo lo dejaria sin remito -- pero corre despues que este script, asi que no
    entra. Si se moviera este script mas tarde en la cadena, esa proteccion se pierde.
    """
    if not util.table_exists(cr, EXISTING_TABLE):
        _logger.warning(
            "No existe la tabla %s: no se sabe que registros existian antes del pase y no se "
            "desactivo ninguno. Revisar que el script pre-odoo haya corrido.",
            EXISTING_TABLE,
        )
        return

    deactivated = 0
    for model, table in TABLE_BY_MODEL.items():
        # Solo los modelos que se pueden archivar. Los otros (ir.model, res.groups, ...) hay que
        # mirarlos a mano: aparecen en el reporte de abajo.
        if not util.table_exists(cr, table) or not util.column_exists(cr, table, "active"):
            continue
        cr.execute(
            SQL(
                """
                UPDATE %(table)s record
                   SET active = false
                 WHERE record.active
                   AND NOT EXISTS (
                         SELECT 1 FROM %(existing)s backup
                          WHERE backup.model = %(model)s AND backup.res_id = record.id
                       )
                   AND NOT EXISTS (
                         SELECT 1 FROM ir_model_data imd
                          WHERE imd.model = %(model)s AND imd.res_id = record.id
                       )
             RETURNING record.id
                """,
                table=SQL.identifier(table),
                existing=SQL.identifier(EXISTING_TABLE),
                model=model,
            )
        )
        record_ids = [row[0] for row in cr.fetchall()]
        if record_ids:
            # Se listan los ids: el registro queda archivado, no borrado, y con esto se puede
            # revertir uno por uno si alguno hacia falta.
            _logger.info(
                "Deactivated %s %s records that did not exist before the upgrade: %s",
                len(record_ids),
                model,
                record_ids,
            )
            deactivated += len(record_ids)
    _logger.info("Deactivated %s counted records that did not exist before the upgrade", deactivated)

    # Los modelos sin `active` no se pueden archivar: se reportan para mirarlos a mano.
    for model, table in TABLE_BY_MODEL.items():
        if not util.table_exists(cr, table) or util.column_exists(cr, table, "active"):
            continue
        cr.execute(
            SQL(
                """
                SELECT count(*)
                  FROM %(table)s record
                 WHERE NOT EXISTS (
                         SELECT 1 FROM %(existing)s backup
                          WHERE backup.model = %(model)s AND backup.res_id = record.id
                       )
                   AND NOT EXISTS (
                         SELECT 1 FROM ir_model_data imd
                          WHERE imd.model = %(model)s AND imd.res_id = record.id
                       )
                """,
                table=SQL.identifier(table),
                existing=SQL.identifier(EXISTING_TABLE),
                model=model,
            )
        )
        count = cr.fetchone()[0]
        if count:
            _logger.warning(
                "%s registros de %s se cuentan como personalizacion y no existian antes del "
                "pase, pero el modelo no se puede archivar: revisarlos a mano.",
                count,
                model,
            )
