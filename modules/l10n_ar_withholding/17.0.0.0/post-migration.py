from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


def migrate_taxes_config(cr):
    query = """update account_tax set
        type_tax_use = 'none',
        l10n_ar_withholding_payment_type = type_tax_use
    where
        type_tax_use in ('customer', 'supplier')
    """
    openupgrade.logged_query(cr, query)


def migrate(cr, version):
    _logger.debug('Running migrate script for l10n_ar_withholding')
    migrate_taxes_config(cr)
