import logging

_logger = logging.getLogger(__name__)

# Backup de la tabla vieja antes de que se carguen los nuevos datos
_backup_table = ("inflation_adjustment_index", "inflation_adjustment_index_bu")


def migrate(cr, version):
    """Hacemos back up de la tabla con los índices de ajuste de inflación y eliminamos la tabla original. Esto lo hacemos porque con la instalación de l10n_ar_account_reports se van a crear los mismos registros que ya existen en dicha tabla y van a quedar repetidos los índices de ajuste por inflación."""

    # Crear backup de la tabla vieja antes de cargar los nuevos datos
    old_table, backup_table = _backup_table
    _logger.info("Creando tabla de respaldo %s a partir de %s", backup_table, old_table)
    cr.execute(f"CREATE TABLE IF NOT EXISTS {backup_table} AS SELECT * FROM {old_table}")

    # Eliminamos tabla inflation_adjustment_index que viene del módulo l10n_ar_account_tax_settlement que en
    # 19 dicho módulo no existe más y la tabla pasa a estar en l10n_ar_account_reports
    cr.execute(f"DELETE FROM {old_table};")
    _logger.info(f"Eliminada la tabla {old_table}")
