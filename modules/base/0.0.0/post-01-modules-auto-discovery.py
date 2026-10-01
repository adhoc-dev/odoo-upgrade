"""Install the modules that scripts marked while `base` was still being upgraded.

With `base` in `to upgrade`, `util.force_install_module` only records the module in
`ENVIRON`. Odoo's own upgrade consumes that list in a `base/0.0.0` post script that this
upgrade path does not have, so without this one the marks are lost.
"""

import logging

from odoo.upgrade.util.const import ENVIRON
from odoo.upgrade.util.modules import _force_install_module, _force_upgrade_of_fresh_module

from oba import run_auto_discovery

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    force_installs = ENVIRON["__modules_auto_discovery_force_installs"]
    _logger.info("Pending installs: %s", sorted(force_installs))
    if not ENVIRON.get("AUTO_DISCOVERY_RAN"):
        run_auto_discovery(cr)
        return

    # Already ran in this -u (apply_module_changes of the jump): a second pass would redo the
    # whole discovery. Only what was marked after it is still pending, and marking again is
    # a no-op for what it already took.
    for module, reason in force_installs.items():
        _force_install_module(cr, module, **({"reason": reason} if reason else {}))
    for module, (init, module_version) in ENVIRON["__modules_auto_discovery_force_upgrades"].items():
        _force_upgrade_of_fresh_module(cr, module, init, module_version)
