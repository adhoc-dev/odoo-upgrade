"""Adhoc helpers for upgrade scripts.

A top-level directory, like ``pre_odoo_scripts/``: Odoo's loader only descends into the
ones named after a module. Importable because ``odoo.modules.module`` appends every
``--upgrade-path`` to ``odoo.upgrade.__path__``, which is where ``odoo.upgrade.util``
comes from too.

Import from the package, not from the modules inside it:

    from odoo.upgrade.oba import add_customer_note
"""

from .customer_note import add_customer_note

__all__ = ["add_customer_note"]
