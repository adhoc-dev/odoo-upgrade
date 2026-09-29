"""Install the modules that scripts marked while `base` was still being upgraded.

With `base` in `to upgrade`, `util.force_install_module` only records the module in
`ENVIRON`. Odoo's own upgrade consumes that list in a `base/0.0.0` post script that this
upgrade path does not have, so without this one the marks are lost.
"""

import logging

from odoo.upgrade import util
from odoo.upgrade.util import modules as util_modules
from odoo.upgrade.util.const import ENVIRON
from odoo.upgrade.util.modules import (
    _force_install_module,
    _force_upgrade_of_fresh_module,
    _trigger_auto_discovery,
)

_logger = logging.getLogger(__name__)


def _run_auto_discovery(cr):
    """`_trigger_auto_discovery` registers every module of the addons path, and a manifest
    that depends on a module that is not there raises: those are skipped, like in
    `pre_upgrade_scripts/180_190/merge_and_renames.py`."""
    original_new_module = util_modules.new_module
    original_new_module_dep = util_modules.new_module_dep

    def safe_new_module(cr, module, deps=(), *args, **kwargs):
        try:
            return original_new_module(cr, module, deps=deps, *args, **kwargs)
        except util.UnknownModuleError as e:
            _logger.info("Skipping module %s due to missing dependencies: %s", module, e)
            return None

    def safe_new_module_dep(cr, module, new_dep):
        try:
            return original_new_module_dep(cr, module, new_dep)
        except util.UnknownModuleError as e:
            _logger.info("Skipping module %s due to missing dependencies: %s", module, e)
            return None

    util_modules.new_module = safe_new_module
    util_modules.new_module_dep = safe_new_module_dep
    try:
        _trigger_auto_discovery(cr)
    finally:
        util_modules.new_module = original_new_module
        util_modules.new_module_dep = original_new_module_dep


def migrate(cr, version):
    force_installs = ENVIRON["__modules_auto_discovery_force_installs"]
    _logger.info("Pending installs: %s", sorted(force_installs))
    if not ENVIRON.get("AUTO_DISCOVERY_RAN"):
        _run_auto_discovery(cr)
        return

    # Already ran in this -u (merge_and_renames in 18 -> 19): a second pass would redo the
    # whole discovery. Only what was marked after it is still pending, and marking again is
    # a no-op for what it already took.
    for module, reason in force_installs.items():
        _force_install_module(cr, module, **({"reason": reason} if reason else {}))
    for module, (init, module_version) in ENVIRON["__modules_auto_discovery_force_upgrades"].items():
        _force_upgrade_of_fresh_module(cr, module, init, module_version)
