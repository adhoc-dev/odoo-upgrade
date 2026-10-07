"""Move the contacts off the Argentine timezones that recent PostgreSQL versions no longer accept.

Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from oba import should_run

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
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["contacts"], position="last"):
        return

    for old_tz, new_tz in TIMEZONES.items():
        cr.execute("UPDATE res_partner SET tz = %s WHERE tz = %s", (new_tz, old_tz))
        if cr.rowcount:
            _logger.info("%s contacts moved from %s to %s", cr.rowcount, old_tz, new_tz)
