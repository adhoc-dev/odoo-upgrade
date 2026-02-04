import logging

from odoo.upgrade import util
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

_model_renames = [
    ("stock.book", "stock.picking.type"),
]

_field_renames = [
    ("stock.picking.type", "stock.picking.type", 'document_type_id', 'l10n_ar_document_type_id'),
    ("stock.picking.type", "stock.picking.type", 'l10n_ar_cai', 'l10n_ar_cai_authorization_code'),
    ("stock.picking.type", "stock.picking.type", 'l10n_ar_cai_due', 'l10n_ar_cai_expiration_date'),
    ("stock.picking.type", "stock.picking.type", 'book_id', 'picking_type_id'),
]

_field_moves = [("report_partner_id", "report_signature_section")]


@openupgrade.migrate()
def migrate(cr, version):
    _logger.debug('Running migrate script for l10n_ar')

    for field in _field_moves:
        # movemos campos report partner id y report signature section de stock.book a stock.picking.type
        util.move_field_to_module(cr, model="stock.book", fieldname=field, old_module="stock.book", new_module="stock.picking.type", skip_inherit=())

    # rename de stock.book a stock.picking.type
    # no usamos el move_field_to_module porque creemos q quedarian duplicados los campos y necesitamos mover la data
    # al nuevo campo que ya existe en stock.picking.type
    openupgrade.rename_models(cr, _model_renames)

    # renombramos los campos viejos a los que ya existen
    openupgrade.rename_fields(cr, _field_renames)

    # necesitamos renombrar xmlids?
    # openupgrade.rename_xmlids(env.cr, _xmlid_renames)
