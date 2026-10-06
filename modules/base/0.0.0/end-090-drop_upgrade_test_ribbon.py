"""Drop the ribbon that the Odoo upgrade platform leaves on a test database.

Only on the last jump of the request: the earlier ones are not handed to anybody.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.upgrade import util
from oba import request_context

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 542.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if not request_context(cr).get("is_last_in_series", True):
        return

    ribbon = util.env(cr).ref("__upgrade__.upg_test_ribbon", raise_if_not_found=False)
    if ribbon:
        ribbon.unlink()
        _logger.info("Upgrade test ribbon dropped")
