import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Actualizamos las referencias para usar la actividad basados en el código de la misma.
    Después de que el módulo carga nuevos registros l10n_ar.arca.activity, actualizamos las foreign keys
    en account_account y res_company para que apunten a estos nuevos registros según los códigos coincidentes.
    """
    new_table = "l10n_ar_arca_activity"
    backup_table = "afip_activity_bu"
    new_field = "l10n_ar_arca_activity_id"
    backup_field = "l10n_ar_afip_activity_id_bu"

    # Actualizar referencias en account_account
    _logger.info("Actualizando referencias %s en account_account", new_field)
    cr.execute(
        f"""
        UPDATE account_account
        SET {new_field} = (
            SELECT new_act.id
            FROM {new_table} new_act
            JOIN {backup_table} old_act ON new_act.code = old_act.code
            WHERE old_act.id = account_account.{backup_field}
        )
        WHERE {backup_field} IS NOT NULL
        """
    )
    _logger.info("Actualizadas %d referencias en account_account", cr.rowcount)

    # Actualizar referencias en res_company
    _logger.info("Actualizando referencias %s en res_company", new_field)
    cr.execute(
        f"""
        UPDATE res_company
        SET {new_field} = (
            SELECT new_act.id
            FROM {new_table} new_act
            JOIN {backup_table} old_act ON new_act.code = old_act.code
            WHERE old_act.id = res_company.{backup_field}
        )
        WHERE {backup_field} IS NOT NULL
        """
    )
    _logger.info("Actualizadas %d referencias en res_company", cr.rowcount)

    # Limpiar referencias huérfanas (actividades que no tienen un código coincidente en los nuevos datos)
    _logger.info("Limpiando referencias huérfanas")
    for table in ["account_account", "res_company"]:
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

    for table in ["account_account", "res_company"]:
        _logger.info("Borrando columna de respaldo %s de %s", backup_field, table)
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {backup_field}")

    _logger.info("Post-migración completada exitosamente")
