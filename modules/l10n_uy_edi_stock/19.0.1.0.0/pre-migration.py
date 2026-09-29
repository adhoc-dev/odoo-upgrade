import logging

_logger = logging.getLogger(__name__)


_backup_table = ('l10n_uy_edi_document_stock_picking_rel', 'l10n_uy_edi_document_stock_picking_rel_bu')


def migrate(cr, version):
    """Backup de la tabla de relación Many2many antes de que sea eliminada por Odoo"""
    _logger.info('Running pre-migration script for l10n_uy_edi_stock')
    old_table, backup_table = _backup_table

    # Verificar si la tabla original existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
    """, (old_table,))

    if not cr.fetchone()[0]:
        _logger.warning("Tabla %s no existe, no se requiere backup", old_table)
        return

    # Eliminar tabla backup anterior si existe para evitar datos obsoletos
    _logger.info("Eliminando tabla backup anterior si existe: %s", backup_table)
    cr.execute(f"DROP TABLE IF EXISTS {backup_table}")

    # Crear backup de la tabla de relación
    _logger.info("Creando tabla de respaldo %s a partir de %s", backup_table, old_table)
    cr.execute(f"CREATE TABLE IF NOT EXISTS {backup_table} AS SELECT * FROM {old_table}")

    # Verificar cantidad de registros respaldados
    cr.execute(f"SELECT COUNT(*) FROM {backup_table}")
    count = cr.fetchone()[0]
    _logger.info("Pre-migración completada exitosamente. Registros respaldados: %s", count)
