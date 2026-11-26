"""Adhoc helpers for upgrade scripts.

A plain package, apart from the upgrade path: ``modules/`` only holds modules. Whoever runs
the scripts puts ``lib/`` on the ``PYTHONPATH``.

Import from the package, not from the modules inside it:

    from oba import add_customer_note, log_message, request_context, should_run
"""

from .customer_note import add_customer_note
from .gates import create_backup, should_back_up, should_run, should_run_pre_odoo
from .jump import jump_versions
from .output import (
    ASSIGNED_TECHNICIAN,
    ASSIGNED_TECHNICIAN_PARTNER,
    BUGFIX_TEAM,
    UPGRADE_PROJECT,
    UPGRADE_TICKET,
    create_record_provider,
    log_message,
    set_breaks,
    set_result,
)
from .request_context import request_context
from .timing import timed

__all__ = [
    "ASSIGNED_TECHNICIAN",
    "ASSIGNED_TECHNICIAN_PARTNER",
    "BUGFIX_TEAM",
    "UPGRADE_PROJECT",
    "UPGRADE_TICKET",
    "add_customer_note",
    "create_backup",
    "create_record_provider",
    "jump_versions",
    "log_message",
    "request_context",
    "set_breaks",
    "set_result",
    "should_back_up",
    "should_run",
    "should_run_pre_odoo",
    "timed",
]


def __getattr__(name):
    # Lazy, and out of __all__: module_changes needs upgrade-util, which add_customer_note
    # callers may not have.
    if name in ("MODULE_CHANGES_FILE", "apply_module_changes", "load_module_changes", "run_auto_discovery"):
        from . import module_changes

        return getattr(module_changes, name)
    # Same reason: render reaches into odoo.http, which the pre_odoo scripts do not have in
    # this shape — they import oba with the Odoo of the source version.
    if name in ("RENDER_OK", "render_page", "render_website", "website_paths"):
        from . import render

        return getattr(render, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
