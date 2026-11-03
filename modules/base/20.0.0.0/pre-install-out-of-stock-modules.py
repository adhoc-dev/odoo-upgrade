"""Install the out-of-stock modules on the databases that already have a shop.

Task 78510: from 20.0, website_sale_stock_hide_unavailable ships with the shop
and is auto_install on website_sale. That only reaches a database that installs
eCommerce from now on: this module already exists in the 19.0 addons path, so
the auto discovery of the upgrade sees it as known and never triggers its
auto_install (it only does that for modules the database has never seen).

The two bridges are new, so discovery does create them -- but it walks the
modules in topological order and force installs afterwards, so when it reaches
them the core module is still uninstalled and their own auto_install does not
fire either. That is why the three are marked here, each guarded by what it
really needs.

It has to live in `base`: during a major upgrade `force_install_module` refuses
to run anywhere else, and here it only records the mark, which
`base/0.0.0/post-01-modules-auto-discovery.py` consumes.
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

REASON = "the shop ships with it from 20.0 (task 78510)"

# Each module with everything that has to be installed for it to make sense.
# Guarding on the real dependencies, and not only on website_sale, is what
# keeps force_install from dragging Inventory or Manufacturing into a database
# that does not have them.
TO_INSTALL = [
    ("website_sale_stock_hide_unavailable", ["website_sale"]),
    ("website_sale_stock_hide_unavailable_stock", ["website_sale", "website_sale_stock"]),
    ("website_sale_stock_hide_unavailable_mrp", ["website_sale", "website_sale_stock", "mrp"]),
]


def migrate(cr, version):
    for module, needs in TO_INSTALL:
        if not util.modules_installed(cr, *needs):
            _logger.info("%s not marked: %s are not all installed", module, needs)
            continue
        util.force_install_module(cr, module, reason=REASON)
        _logger.info("%s marked for install", module)
