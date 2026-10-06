"""Move the contacts off the Argentine timezones that recent PostgreSQL versions no longer accept.

Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.upgrade import util
from oba import request_context

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 1812.
FIRST_TARGET_VERSION = 20
TIMEZONES = {
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Rosario": "America/Argentina/Cordoba",
    "America/Cordoba": "America/Argentina/Cordoba",
    "America/Mendoza": "America/Argentina/Mendoza",
    "America/Salta": "America/Argentina/Salta",
    "America/Jujuy": "America/Argentina/Jujuy",
}


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if not util.module_installed(cr, "contacts"):
        return

    if not request_context(cr).get("is_last_in_series", True):
        return

    for old_tz, new_tz in TIMEZONES.items():
        cr.execute("UPDATE res_partner SET tz = %s WHERE tz = %s", (new_tz, old_tz))
        if cr.rowcount:
            _logger.info("%s contacts moved from %s to %s", cr.rowcount, old_tz, new_tz)
