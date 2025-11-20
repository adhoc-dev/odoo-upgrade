import logging
import sys

from odoo.tools import SQL
from odoo.upgrade import util
from odoo.upgrade.util.modules import _trigger_auto_discovery

_logger = logging.getLogger(__name__)

MERGE_MODULES = [("l10n_ar_tax_ratio", "l10n_ar_tax")]
RENAMED_MODULES = []
RENAMED_XMLIDS = []


def migrate(cr, version):
    _logger.info("Running 'merge_and_renames' script for version %s", version)

    # Monkey patch new_module to avoid crashing on missing dependencies
    util_modules = sys.modules["odoo.upgrade.util.modules"]
    original_new_module = util_modules.new_module

    def safe_new_module(cr, module, deps=(), *args, **kwargs):
        try:
            return original_new_module(cr, module, deps=deps, *args, **kwargs)
        except util.UnknownModuleError as e:
            _logger.warning("Skipping module %s due to missing dependencies: %s", module, e)
            return None

    util_modules.new_module = safe_new_module

    try:
        _trigger_auto_discovery(cr)
    finally:
        # Restore original function just in case
        util_modules.new_module = original_new_module

    for old, into in MERGE_MODULES:
        util.merge_module(cr, old, into, update_dependers=False)
    for old, into in RENAMED_MODULES:
        util.rename_module(cr, old, into)
    for old, into in RENAMED_XMLIDS:
        util.rename_xmlid(cr, old, into)

    version = float(".".join(version.split(".")[0:2]))  # Version is str, ex. '18.0.1.3'
    version_string = f"{version - 1}.0.0"
    cr.execute(
        SQL(
            """
        UPDATE ir_module_module
        SET latest_version = %(version)s
        WHERE latest_version IS NULL AND state = 'installed'
        """,
            version=version_string,
        )
    )
