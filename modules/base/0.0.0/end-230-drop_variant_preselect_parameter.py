"""Drop the system parameter of website_sale_stock_variant_preselect.

The module is not migrated to 20: Odoo 20 already opens the product on the first variant
with stock and shows the "out of stock" ribbon only when every variant is sold out. Its
switch, ``website_sale_stock_variant_preselect.enabled``, was set by hand and has no
xmlid, so removing the module does not take it along.

In ``modules/base/0.0.0`` because the module has no code in 20 and its own folders never
run. The module is still ``to upgrade`` here, which ``util.module_installed`` counts as
installed.
"""

import logging

from oba import should_run

_logger = logging.getLogger(__name__)

MODULE = "website_sale_stock_variant_preselect"
PARAMETER = "website_sale_stock_variant_preselect.enabled"
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=[MODULE]):
        return

    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (PARAMETER,))
    if cr.rowcount:
        _logger.info("System parameter %s dropped", PARAMETER)
