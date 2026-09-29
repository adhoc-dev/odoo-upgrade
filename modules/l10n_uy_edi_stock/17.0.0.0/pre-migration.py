from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


_column_copy = {
    'stock_picking': [
        ('l10n_uy_cfe_state', 'l10n_uy_cfe_state_bu', None),
        ('l10n_uy_cfe_uuid', 'l10n_uy_cfe_uuid_bu', None),
        ('l10n_uy_cfe_file', 'l10n_uy_cfe_file_bu', None),
        ('l10n_uy_ucfe_msg', 'l10n_uy_ucfe_msg_bu', None),
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_bu', None),
        ('l10n_uy_cfe_pdf', 'l10n_uy_cfe_pdf_bu', None),
    ],
}

_field_renames = [
    ('stock.picking', 'stock_picking', 'l10n_uy_cfe_state', 'l10n_uy_edi_cfe_state'),
    ('stock.picking', 'stock_picking', 'l10n_uy_cfe_file', 'edi_pdf_report_id'),
]


def migrate(cr, version):
    # backup de columnas que nos interesan antes de que se borren
    _logger.info('Running migrate script for l10n_uy_edi_stock')
    env = api.Environment(cr, SUPERUSER_ID, {})
    openupgrade.copy_columns(env.cr, _column_copy)
    openupgrade.rename_fields(env, _field_renames)
