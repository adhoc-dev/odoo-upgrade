"""Module merges and renames of one major version jump.

    from oba import apply_module_changes

    MERGE_MODULES = [("l10n_ar_tax_ratio", "l10n_ar_tax")]
    RENAMED_MODULES = []
    RENAMED_XMLIDS = []

    def migrate(cr, version):
        apply_module_changes(cr, version, MERGE_MODULES, RENAMED_MODULES, RENAMED_XMLIDS)

The code is the same on every jump; each ``scripts/pre_upgrade/<jump>/merge_and_renames.py``
only declares its lists. Call it on every jump, even with empty lists: it also runs the
module auto-discovery and fills ``latest_version``.

Public API: :func:`apply_module_changes`. Everything else is internal.
"""

import logging
import sys

from odoo.tools import SQL
from odoo.upgrade import util
from odoo.upgrade.util.modules import _trigger_auto_discovery

_logger = logging.getLogger(__name__)


def apply_module_changes(cr, version, merges=(), renames=(), xmlid_renames=()):
    """Merge and rename modules and xmlids of this jump.

    :param merges: ``(old, into)`` pairs, applied with :func:`util.merge_module`.
    :param renames: ``(old, new)`` module pairs, applied with :func:`util.rename_module`.
    :param xmlid_renames: ``(old, new)`` xmlid pairs, applied with :func:`util.rename_xmlid`.
    """
    _logger.info("Applying module merges and renames for version %s", version)
    _auto_discovery_skipping_missing_deps(cr)
    for old, into in merges:
        _merge_keeping_target_state(cr, old, into)
    for old, into in renames:
        util.rename_module(cr, old, into)
    for old, into in xmlid_renames:
        util.rename_xmlid(cr, old, into)
    _fill_latest_version(cr, version)


def _auto_discovery_skipping_missing_deps(cr):
    # Monkey patch new_module to avoid crashing on missing dependencies
    util_modules = sys.modules["odoo.upgrade.util.modules"]
    original_new_module = util_modules.new_module
    original_new_module_dep = util_modules.new_module_dep

    def safe_new_module(cr, module, deps=(), *args, **kwargs):
        try:
            return original_new_module(cr, module, deps=deps, *args, **kwargs)
        except util.UnknownModuleError as e:
            _logger.info(
                "Skipping module %s due to missing dependencies: %s", module, e
            )
            return None

    def safe_new_module_dep(cr, module, new_dep):
        try:
            return original_new_module_dep(cr, module, new_dep)
        except util.UnknownModuleError as e:
            _logger.info(
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


def _merge_keeping_target_state(cr, old, into):
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
    # Skip if the old module is not in the database: there is nothing to merge and
    # we must not touch the target module's state (it is already correctly named).
    if not old_state:
        _logger.info("Module %s not found, skipping merge into %s", old, into)
        return
    old_state = old_state[0]
    util.merge_module(cr, old, into, update_dependers=False)
    # Ensure the target module is marked for upgrade — only when the old
    # module was actually in use. If it only existed as a not-installed
    # leftover row, keep the target's original state: copying the old state
    # silently uninstalled active targets (e.g. l10n_ar_tax overwritten by
    # l10n_ar_tax_ratio's 'uninstalled').
    if old_state in ("installed", "to upgrade"):
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


def _fill_latest_version(cr, version):
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
