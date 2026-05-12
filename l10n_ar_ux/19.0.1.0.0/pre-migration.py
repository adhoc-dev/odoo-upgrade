import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

# Backup de la tabla vieja antes de que se carguen los nuevos datos
_backup_table = ("afip_activity", "afip_activity_bu")

# Columnas a copiar en las tablas que referencian la actividad
_column_copy = {
    "account_account": [
        ("l10n_ar_afip_activity_id", "l10n_ar_afip_activity_id_bu", None),
    ],
    "res_company": [
        ("l10n_ar_afip_activity_id", "l10n_ar_afip_activity_id_bu", None),
    ],
}


def migrate(cr, version):
    """Hacemos back up de los datos de actividad antiguos y preparamos para la carga de nuevos datos."""

    raise Exception("[TEST] Forced failure to test upgrading error log entry")
    # Crear backup de la tabla vieja antes de cargar los nuevos datos
    old_table, backup_table = _backup_table
    _logger.info("Creando tabla de respaldo %s a partir de %s", backup_table, old_table)
    cr.execute(
        f"CREATE TABLE IF NOT EXISTS {backup_table} AS SELECT * FROM {old_table}"
    )

    # Copiar columnas viejas a columnas de backup en tablas referenciadas
    _logger.info("Copiando columnas de las columnas viejas a las columnas de respaldo")
    openupgrade.copy_columns(cr, _column_copy)

    _logger.info("Pre-migración completada exitosamente")
