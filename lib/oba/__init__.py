"""Adhoc helpers for upgrade scripts.

A plain package, apart from the upgrade path: ``modules/`` only holds modules. Whoever runs
the scripts puts ``lib/`` on the ``PYTHONPATH``.

Import from the package, not from the modules inside it:

    from oba import add_customer_note
"""

from .customer_note import add_customer_note

__all__ = ["add_customer_note"]
