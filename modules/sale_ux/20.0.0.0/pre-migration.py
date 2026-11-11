import logging

_logger = logging.getLogger(__name__)

# sale_product_uom_price (19) is merged into sale_ux in 20: scripts/pre_upgrade/190_200/module_changes.json.
OLD_PARAM = "sale_product_uom_price.report_in_product_uom"
NEW_PARAM = "sale_ux.report_in_product_uom"


def migrate(cr, version):
    """Keep the "Show Product Unit on Quotations" setting of sale_product_uom_price.

    In 19 the setting lived in its own module and stored the system parameter
    `sale_product_uom_price.report_in_product_uom`. In 20 the module is merged into sale_ux, which
    reads `sale_ux.report_in_product_uom`: without this, the databases that printed quotations in
    the product unit go back to the packaging unit.
    """
    _logger.info("Running pre-migration for sale_ux version %s", version)

    cr.execute(
        """
        UPDATE ir_config_parameter
           SET key = %s
         WHERE key = %s
           AND NOT EXISTS (SELECT 1 FROM ir_config_parameter WHERE key = %s)
        """,
        [NEW_PARAM, OLD_PARAM, NEW_PARAM],
    )
    if cr.rowcount:
        _logger.info("Parameter %s renamed to %s", OLD_PARAM, NEW_PARAM)
    # Left over only when both keys were there: the sale_ux one already rules.
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", [OLD_PARAM])
