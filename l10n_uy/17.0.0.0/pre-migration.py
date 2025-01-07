from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)

_column_copy = {
    'account_tax_group': [
        ('l10n_uy_vat_code', 'l10n_uy_vat_code_bu', None),
    ]
}

def migrate(cr, version):
    _logger.info('Running pre-migrate script for l10n_uy')
    env = api.Environment(cr, SUPERUSER_ID, {})
    # TODO hacer los rename
    _xmlid_renames = [
        ('l10n_uy.tax_group_vat_22', 'l10n_uy.tax_group_iva_22'),
        ('l10n_uy.tax_group_vat_10', 'l10n_uy.tax_group_iva_10'),
        ('l10n_uy.tax_group_vat_exempt', 'l10n_uy.tax_group_exenton'),
        ('l10n_uy.adenda_exoneracion_impuesto_renta', 'l10n_uy_edi_ux.adenda_exoneracion_impuesto_renta'),
    ]

    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
    openupgrade.copy_columns(env.cr, _column_copy)
