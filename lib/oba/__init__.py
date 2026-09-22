"""Adhoc helpers for upgrade scripts.

A plain package, apart from the upgrade path: ``modules/`` only holds modules. Whoever runs
the scripts puts ``lib/`` on the ``PYTHONPATH``.

Import from the package, not from the modules inside it:

    from oba import add_customer_note, log_message, request_context
"""

from .customer_note import add_customer_note
from .output import log_message, set_breaks, set_result
from .request_context import request_context

__all__ = ["add_customer_note", "log_message", "request_context", "set_breaks", "set_result"]
