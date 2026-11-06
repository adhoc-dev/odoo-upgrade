import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

OLD_MODEL = "l10n_ar.payment.withholding"


def migrate(cr, version):
    """Remove the 19 withholding lines model, which the post-migration already moved to 20.

    Odoo deletes its ir.model when the module is updated, but not its table: the model is no longer
    in the registry, so the table and what points to it stay behind. This runs after every
    post-migration, so the modules that added columns to the old lines (l10n_ar_arba_ws,
    l10n_ar_tax_backward_compatibility) have to read them in their post-migration, through
    l10n_ar_payment_withholding_map_bu, which stays.
    """
    _logger.info("Running end-migration for l10n_ar_tax version %s", version)
    if not util.table_exists(cr, "l10n_ar_payment_withholding"):
        return
    util.remove_model(cr, OLD_MODEL)
    _logger.info("Model %s and its table removed", OLD_MODEL)
