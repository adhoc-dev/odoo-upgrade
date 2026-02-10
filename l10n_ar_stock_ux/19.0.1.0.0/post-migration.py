import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.debug('Running migrate script for l10n_ar_stock_ux')

    # Verificar si existe la tabla de backup antes de proceder
    if not sql.table_exists(cr, 'stock_book_bu'):
        _logger.warning("La tabla stock_book_bu no existe; se omite la migración de datos")
        return

    # Actualizamos stock picking type con los datos de stock book solo para report signature section,
    # que lo tenemos en l10n_ar_stock_ux
    _logger.info("Actualizando datos de contacto de reporte en stock_picking_type con los datos de stock_book_bu")
    query = """
    UPDATE stock_picking_type
    SET
        report_partner_id = book.report_partner_id,
        report_signature_section = book.report_signature_section
    FROM stock_book_bu book
    WHERE stock_picking_type.id = book.id
    """
    cr.execute(query)
