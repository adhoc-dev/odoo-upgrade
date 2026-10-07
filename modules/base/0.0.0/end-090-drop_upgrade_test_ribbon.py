"""Drop the ribbon that the Odoo upgrade platform leaves on a test database.

Only on the last jump of the request: the earlier ones are not handed to anybody.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.upgrade import util
from oba import should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 542.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, position="last"):
        return

    ribbon = util.env(cr).ref("__upgrade__.upg_test_ribbon", raise_if_not_found=False)
    if ribbon:
        ribbon.unlink()
        _logger.info("Upgrade test ribbon dropped")
