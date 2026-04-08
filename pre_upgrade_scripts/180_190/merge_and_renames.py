import logging
import sys

from odoo.tools import SQL
from odoo.upgrade import util
from odoo.upgrade.util.modules import _trigger_auto_discovery

_logger = logging.getLogger(__name__)

MERGE_MODULES = [
    ("l10n_ar_tax_ratio", "l10n_ar_tax"),
    ("sale_exceptions_ignore_approve", "sale_exception_ux"),
    ("sale_three_discounts", "sale_triple_discount"),
    ("l10n_ar_stock_custom", "l10n_ar_stock"),
    ("l10n_ar_stock_adhoc", "l10n_ar_stock"),
    ("l10n_uy_reports_custom", "l10n_uy_reports"),
    ("l10n_uy_edi_stock_custom", "l10n_uy_edi_stock"),
]
RENAMED_MODULES = []
RENAMED_XMLIDS = []


def migrate(cr, version):
    _logger.info("Running 'merge_and_renames' script for version %s", version)

    # Monkey patch new_module to avoid crashing on missing dependencies
    util_modules = sys.modules["odoo.upgrade.util.modules"]
    original_new_module = util_modules.new_module
    original_new_module_dep = util_modules.new_module_dep

    def safe_new_module(cr, module, deps=(), *args, **kwargs):
        try:
            return original_new_module(cr, module, deps=deps, *args, **kwargs)
        except util.UnknownModuleError as e:
            _logger.warning(
                "Skipping module %s due to missing dependencies: %s", module, e
            )
            return None

    def safe_new_module_dep(cr, module, new_dep):
        try:
            return original_new_module_dep(cr, module, new_dep)
        except util.UnknownModuleError as e:
            _logger.warning(
                "Skipping module %s due to missing dependencies: %s", module, e
            )
            return None

    util_modules.new_module = safe_new_module
    util_modules.new_module_dep = safe_new_module_dep

    try:
        _trigger_auto_discovery(cr)
    finally:
        # Restore original function just in case
        util_modules.new_module = original_new_module
        util_modules.new_module_dep = original_new_module_dep

    for old, into in MERGE_MODULES:
        cr.execute(
            SQL(
                """
                SELECT state FROM ir_module_module
                 WHERE name = %(name)s
                """,
                name=old,
            )
        )
        old_state = cr.fetchone()
        old_state = old_state and old_state[0] or "uninstalled"
        util.merge_module(cr, old, into, update_dependers=False)
        # Ensure the target module is marked for upgrade
        cr.execute(
            SQL(
                """
                UPDATE ir_module_module
                    SET state = %(upgrade_state)s
                    WHERE name = %(name)s
                """,
                name=into,
                upgrade_state=old_state,
            )
        )
    for old, into in RENAMED_MODULES:
        util.rename_module(cr, old, into)
    for old, into in RENAMED_XMLIDS:
        util.rename_xmlid(cr, old, into)

    version = float(".".join(version.split(".")[0:2]))  # Version is str, ex. '18.0.1.3'
    version_string = f"{version}.0.0"
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
