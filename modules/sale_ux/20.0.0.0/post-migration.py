import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Settings that sale_ux 19 stored as system parameters and that 20 no longer reads.
SHOW_IMAGE_PARAM = "sale_ux.show_product_image_on_report"
UPDATE_PRICES_PARAM = "sale_ux.update_prices_automatically"
FALSE_VALUES = ("", "false", "0", "no")


def migrate(cr, version):
    """Pass the "show product image on the quotation report" setting to the native one.

    In 19 sale_ux showed the product image on the quotation report when the system parameter
    `sale_ux.show_product_image_on_report` was set, for every company. Odoo 20 shows it
    natively with `res.company.display_product_images_on_so` (default False), so without this
    the databases that had the setting on lose the images on the quotations (task 76366).

    The parameter was global: every company gets the same value. Companies are not touched when
    the parameter was not set. The two parameters are deleted afterwards because nothing reads
    them anymore (`sale_ux.update_prices_automatically` went away with the setting that
    recomputed prices when changing the pricelist, which 20 does always).
    """
    _logger.info("Running post-migration for sale_ux version %s", version)

    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", [SHOW_IMAGE_PARAM])
    row = cr.fetchone()
    enabled = bool(row and row[0] and row[0].strip().lower() not in FALSE_VALUES)

    if enabled:
        if not util.column_exists(cr, "res_company", "display_product_images_on_so"):
            # Not "the setting was off": nobody could migrate it. Keep the parameter to retry.
            _logger.warning("res_company.display_product_images_on_so does not exist: the setting was not migrated")
            return
        cr.execute("UPDATE res_company SET display_product_images_on_so = TRUE")
        _logger.info("Product images on quotations turned on for %s companies", cr.rowcount)

    cr.execute(
        "DELETE FROM ir_config_parameter WHERE key IN %s",
        [(SHOW_IMAGE_PARAM, UPDATE_PRICES_PARAM)],
    )
