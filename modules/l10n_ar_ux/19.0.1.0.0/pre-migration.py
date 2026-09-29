import logging

from odoo.upgrade import util
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
    """Hacemos back up de los datos de actividad antiguos y preparamos para la carga de nuevos datos.

    Idempotente: en un re-run del -u la columna vieja puede no existir (Odoo la
    dropea al terminar la carga) o el backup puede estar hecho; en ambos casos
    se saltea sin fallar.
    """

    # Crear backup de la tabla vieja antes de cargar los nuevos datos
    old_table, backup_table = _backup_table
    if not util.table_exists(cr, old_table):
        _logger.info("Table %s does not exist, skipping backup", old_table)
    elif util.table_exists(cr, backup_table):
        _logger.info("Backup table %s already exists, skipping", backup_table)
    else:
        _logger.info("Creando tabla de respaldo %s a partir de %s", backup_table, old_table)
        cr.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM {old_table}")

    # Copiar columnas viejas a columnas de backup en tablas referenciadas
    column_copy = {}
    for table, specs in _column_copy.items():
        pending = []
        for old, new, field_type in specs:
            if not util.column_exists(cr, table, old):
                _logger.info("Column %s.%s does not exist, skipping backup", table, old)
            elif util.column_exists(cr, table, new):
                _logger.info("Backup column %s.%s already exists, skipping", table, new)
            else:
                pending.append((old, new, field_type))
        if pending:
            column_copy[table] = pending

    if column_copy:
        _logger.info("Copiando columnas de las columnas viejas a las columnas de respaldo")
        openupgrade.copy_columns(cr, column_copy)

    _logger.info("Pre-migración completada exitosamente")
