from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    _logger.info('Running pre-migrate script for l10n_uy')
    # TODO hacer los rename
    _xmlid_renames = [
        ('l10n_uy.tax_group_vat_22', 'l10n_uy.tax_group_iva_22'),
        ('l10n_uy.tax_group_vat_10', 'l10n_uy.tax_group_iva_10'),
        ('l10n_uy.tax_group_vat_exempt', 'l10n_uy.tax_group_exenton'),
        ('l10n_uy.adenda_exoneracion_impuesto_renta', 'l10n_uy_edi_ux.adenda_exoneracion_impuesto_renta'),
    ]

    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
