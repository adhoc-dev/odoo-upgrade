import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.debug('Running migrate script for l10n_ar_stock')

    # Verificar si existe la tabla de backup antes de proceder
    if not sql.table_exists(cr, 'stock_book_bu'):
        _logger.warning("La tabla stock_book_bu no existe; se omite la migración de datos")
        return

    # Actualizar stock picking type con los datos de stock book
    _logger.info("Actualizando stock_picking_type con los datos de stock_book_bu")
    query = """
    UPDATE stock_picking_type
    SET
        l10n_ar_document_type_id = book.document_type_id,
        l10n_ar_cai_authorization_code = book.l10n_ar_cai,
        l10n_ar_cai_expiration_date = book.l10n_ar_cai_due
    FROM stock_book_bu book
    WHERE stock_picking_type.id = book.id
    """
    cr.execute(query)
