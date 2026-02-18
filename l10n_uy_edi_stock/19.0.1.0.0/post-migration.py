import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migra datos de la relación Many2many antigua al nuevo campo Many2one l10n_uy_edi_reference"""
    _logger.info('Running post-migration script for l10n_uy_edi_stock')

    backup_table = 'l10n_uy_edi_document_stock_picking_rel_bu'

    # Verificar si la tabla backup existe
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = %s
        )
    """, (backup_table,))

    if not cr.fetchone()[0]:
        _logger.warning("Tabla backup %s no existe, no se requiere migración de datos", backup_table)
        return

    # Migrar datos desde la tabla backup a la nueva estructura
    # Se toma el último documento EDI asociado a cada picking (ORDER BY DESC LIMIT 1)
    query = """
        UPDATE stock_picking
        SET l10n_uy_edi_reference = (
            SELECT rel.l10n_uy_edi_document_id
            FROM l10n_uy_edi_document_stock_picking_rel_bu rel
            WHERE rel.stock_picking_id = stock_picking.id
            ORDER BY rel.l10n_uy_edi_document_id DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM l10n_uy_edi_document_stock_picking_rel_bu rel2
            WHERE rel2.stock_picking_id = stock_picking.id
        )
    """

    _logger.info("Migrando datos de relación Many2many a campo Many2one l10n_uy_edi_reference")
    cr.execute(query)
    _logger.info("Migración de datos completada. Registros actualizados: %s", cr.rowcount)
