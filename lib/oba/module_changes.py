"""Module merges and renames of one major version jump.

Each jump declares them in ``scripts/pre_upgrade/<jump>/module_changes.json``, a copy of
``scripts/pre_upgrade/module_changes.template.json``:

    {
        "merge_modules": [["l10n_ar_tax_ratio", "l10n_ar_tax"]],
        "renamed_modules": [],
        "renamed_xmlids": []
    }

and ``scripts/pre_upgrade/always/merge_and_renames.py`` applies the file of the jump in
course. A jump without the file logs a warning and only runs the module auto-discovery, which
``base/0.0.0/post-01-modules-auto-discovery.py`` runs anyway.

Public API: :data:`MODULE_CHANGES_FILE`, :func:`apply_module_changes`,
:func:`load_module_changes` and :func:`run_auto_discovery`.
"""

import json
import logging
import os

# No odoo.tools.SQL: post-01 imports this module on every jump, also to versions before 17.
from odoo.upgrade import util
from odoo.upgrade.util import modules as util_modules

_logger = logging.getLogger(__name__)

MODULE_CHANGES_FILE = "module_changes.json"
MODULE_CHANGES_KEYS = ("merge_modules", "renamed_modules", "renamed_xmlids")


def apply_module_changes(cr, version, merges=(), renames=(), xmlid_renames=()):
    """Merge and rename modules and xmlids of this jump.

    :param merges: ``(old, into)`` pairs, applied with :func:`util.merge_module`.
    :param renames: ``(old, new)`` module pairs, applied with :func:`util.rename_module`.
    :param xmlid_renames: ``(old, new)`` xmlid pairs, applied with :func:`util.rename_xmlid`.
    """
    _logger.info("Applying module merges and renames for version %s", version)
    # Before the discovery: it registers the new name from the addons path, and the rename
    # would then break the unique module name.
    for old, new in renames:
        util.rename_module(cr, old, new)
    # After it, merges need the target registered.
    run_auto_discovery(cr)
    for old, into in merges:
        _merge_keeping_target_state(cr, old, into)
    for old, new in xmlid_renames:
        util.rename_xmlid(cr, old, new)
    _fill_latest_version(cr, version)


def load_module_changes(path):
    """Read the merges and renames of a ``module_changes.json``.

    :return: the ``merges``, ``renames`` and ``xmlid_renames`` of :func:`apply_module_changes`,
        as lists of ``(old, new)`` pairs. All empty if the file does not exist.
    :raise ValueError: on a file that is not an object of lists, an unknown key or a pair that
        is not two names, so a typo does not skip a merge without notice.
    """
    if not os.path.exists(path):
        # A badly built jump folder (a runbot build of saas~19.4) lands here too.
        _logger.warning("No module changes file at %s: no module is merged or renamed", path)
        return ([], [], [])
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold an object with the keys {list(MODULE_CHANGES_KEYS)}")
    unknown = sorted(set(data) - set(MODULE_CHANGES_KEYS))
    if unknown:
        raise ValueError(f"Unknown keys in {path}: {unknown}")
    changes = []
    for key in MODULE_CHANGES_KEYS:
        pairs = data.get(key, [])
        if not isinstance(pairs, list) or not all(_is_pair(pair) for pair in pairs):
            raise ValueError(f"{key} in {path} must hold [old, new] pairs of names")
        changes.append([tuple(pair) for pair in pairs])
    return tuple(changes)


def _is_pair(pair):
    return isinstance(pair, list) and len(pair) == 2 and all(isinstance(name, str) for name in pair)


def run_auto_discovery(cr):
    """Register the modules of the addons path, skipping those with a missing dependency.

    ``_trigger_auto_discovery`` raises on a manifest that depends on a module that is not
    in the addons path.
    """
    original_new_module = util_modules.new_module
    original_new_module_dep = util_modules.new_module_dep
    util_modules.new_module = _skipping_missing_deps(original_new_module)
    util_modules.new_module_dep = _skipping_missing_deps(original_new_module_dep)
    try:
        util_modules._trigger_auto_discovery(cr)
    finally:
        util_modules.new_module = original_new_module
        util_modules.new_module_dep = original_new_module_dep


def _skipping_missing_deps(func):
    def wrapper(cr, module, *args, **kwargs):
        try:
            return func(cr, module, *args, **kwargs)
        except util.UnknownModuleError as e:
            _logger.info("Skipping module %s due to missing dependencies: %s", module, e)
            return None

    return wrapper


def _merge_keeping_target_state(cr, old, into):
    cr.execute("SELECT state FROM ir_module_module WHERE name = %s", [old])
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
        cr.execute("UPDATE ir_module_module SET state = %s WHERE name = %s", [old_state, into])


def _fill_latest_version(cr, version):
    version = float(".".join(version.split(".")[0:2]))  # Version is str, ex. '18.0.1.3'
    cr.execute(
        "UPDATE ir_module_module SET latest_version = %s WHERE latest_version IS NULL AND state = 'installed'",
        [f"{version}.0.0"],
    )
