import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move the companies from our ARCA provider to the native one.

    In 19 the module added the 'afip' value to res.company.currency_provider. In 20
    the module no longer adds it and l10n_ar_edi brings the native 'arca' value.
    Odoo does not map one to the other, so without this the companies keep a value
    that no provider handles and their rates stop updating.

    Idempotent: a second run finds no 'afip' rows.
    """
    _logger.info("Running pre-migration for l10n_ar_currency_update %s", version)
    cr.execute(
        SQL(
            "UPDATE res_company SET currency_provider = %(new)s WHERE currency_provider = %(old)s",
            new="arca",
            old="afip",
        )
    )
    _logger.info("Companies moved from the 'afip' to the 'arca' currency provider: %s", cr.rowcount)
