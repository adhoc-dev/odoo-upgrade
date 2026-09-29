import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Actualizamos las referencias para usar la actividad basados en el código de la misma.
    Después de que el módulo carga nuevos registros l10n_ar.arca.activity, actualizamos las foreign keys
    en account_account y res_company para que apunten a estos nuevos registros según los códigos coincidentes.

    Idempotente: si el backup ya fue consumido en una corrida anterior no hay nada
    que remapear. Si la columna destino no existe todavía (l10n_ar_reports_simple
    no cargado), se conserva el backup para no perder el dato.
    """
    new_table = "l10n_ar_arca_activity"
    backup_table = "afip_activity_bu"
    new_field = "l10n_ar_arca_activity_id"
    backup_field = "l10n_ar_afip_activity_id_bu"
    tables = ["account_account", "res_company"]

    missing = [table for table in tables if not util.column_exists(cr, table, new_field)]
    if missing or not util.table_exists(cr, new_table):
        _logger.warning(
            "Column %s not found in %s (l10n_ar_reports_simple not loaded?), keeping the activity backups",
            new_field,
            ", ".join(missing) or new_table,
        )
        return

    if util.table_exists(cr, backup_table):
        for table in tables:
            if not util.column_exists(cr, table, backup_field):
                _logger.info("Backup column %s.%s does not exist, nothing to remap", table, backup_field)
                continue
            _logger.info("Actualizando referencias %s en %s", new_field, table)
            cr.execute(
                f"""
                UPDATE {table}
                SET {new_field} = (
                    SELECT new_act.id
                    FROM {new_table} new_act
                    JOIN {backup_table} old_act ON new_act.code = old_act.code
                    WHERE old_act.id = {table}.{backup_field}
                )
                WHERE {backup_field} IS NOT NULL
                """
            )
            _logger.info("Actualizadas %d referencias en %s", cr.rowcount, table)
    else:
        _logger.info("Backup table %s does not exist, nothing to remap", backup_table)

    # Limpiar referencias huérfanas (actividades que no tienen un código coincidente en los nuevos datos)
    _logger.info("Limpiando referencias huérfanas")
    for table in tables:
        cr.execute(
            f"""
            UPDATE {table}
            SET {new_field} = NULL
            WHERE {new_field} IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM {new_table} WHERE id = {table}.{new_field}
            )
            """
        )
        if cr.rowcount:
            _logger.info(
                "Limpiadas %d referencias huérfanas en la tabla '%s'", cr.rowcount, table
            )

    # Borrar tablas y columnas backup
    _logger.info("Borrando tabla de respaldo %s", backup_table)
    cr.execute(f"DROP TABLE IF EXISTS {backup_table}")

    for table in tables:
        _logger.info("Borrando columna de respaldo %s de %s", backup_field, table)
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {backup_field}")

    _logger.info("Post-migración completada exitosamente")
