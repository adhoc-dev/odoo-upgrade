import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Move the invoice PDF legend from our backport to the native field.

    In 19 the module backported odoo/enterprise#102032 as l10n_ar_invoice_pdf_legend_ux
    and stopped reading l10n_ar_edi's l10n_ar_show_withholding_legend. In 20
    l10n_ar_edi brings l10n_ar_invoice_pdf_legend, with the same keys, and the module
    drops its field: its column is removed at the end of the update, after this script.

    Empty values are copied too: the native field must not keep a legend that the
    company had removed in 19, whatever the old boolean says.

    Idempotent: a second run finds both columns equal, or ours already removed.
    """
    _logger.info("Running post-migration for l10n_ar_edi_ux %s", version)
    if not util.column_exists(cr, "res_company", "l10n_ar_invoice_pdf_legend_ux"):
        _logger.info("No l10n_ar_invoice_pdf_legend_ux column: nothing to move")
        return
    cr.execute(
        SQL(
            """
            UPDATE res_company
               SET l10n_ar_invoice_pdf_legend = l10n_ar_invoice_pdf_legend_ux
             WHERE l10n_ar_invoice_pdf_legend IS DISTINCT FROM l10n_ar_invoice_pdf_legend_ux
            """
        )
    )
    _logger.info("Companies whose invoice PDF legend was moved to the native field: %s", cr.rowcount)
