"""Adhoc helpers for upgrade scripts.

A plain package, apart from the upgrade path: ``modules/`` only holds modules. Whoever runs
the scripts puts ``lib/`` on the ``PYTHONPATH``.

Import from the package, not from the modules inside it:

    from oba import add_customer_note, log_message, request_context
"""

from .customer_note import add_customer_note
from .output import log_message, set_breaks, set_result
from .request_context import request_context

__all__ = [
    "add_customer_note",
    "log_message",
    "request_context",
    "set_breaks",
    "set_result",
]


def __getattr__(name):
    # Lazy, and out of __all__: module_changes needs upgrade-util, which add_customer_note
    # callers may not have.
    if name in ("apply_module_changes", "run_auto_discovery"):
        from . import module_changes

        return getattr(module_changes, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
