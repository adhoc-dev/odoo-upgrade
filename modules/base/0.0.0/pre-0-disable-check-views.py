"""Delay the view check while the modules load, instead of letting it stop the ``-u``.

A view can fail only for a while during the load: an orphan that ``_process_end`` purges
later, or a view that a module loaded after it fixes. So a failing check is logged and the
view is kept in ``IrUiView._upgrade_delayed_view_ids``; ``end-890-check_delayed_views.py``
checks those again once everything is loaded. The original check stays reachable as
``IrUiView._upgrade_original_check_xml``, for the scripts that need to know whether a view
really fails (``end-210-check_personalizations.py``). Same approach as the fixdb of
``saas_client`` (``fix_modules``), which runs after the upgrade.

In ``modules/base/0.0.0`` so it runs on every jump from 20 on; until 19 each version folder
has its own copy.
"""

import logging

from oba import should_run, timed

_logger = logging.getLogger(__name__)


def _check_xml(self):
    try:
        # A database error inside the check must not leave the -u on an aborted transaction.
        with self.env.cr.savepoint():
            return type(self)._upgrade_original_check_xml(self)
    except Exception as e:
        type(self)._upgrade_delayed_view_ids.update(self.ids)
        _logger.warning("Delaying view check for view(s) %s: %s", self.ids, e)


@timed
def migrate(cr, version):
    if not should_run(cr, version):
        return
    # Imported here: the folder loads on every jump, and before 19 the class is View
    from odoo.addons.base.models.ir_ui_view import IrUiView

    # Kept from the first run: a second -u in the same process must not save the patch itself.
    if not hasattr(IrUiView, "_upgrade_original_check_xml"):
        IrUiView._upgrade_original_check_xml = IrUiView._check_xml
    IrUiView._upgrade_delayed_view_ids = set()
    IrUiView._check_xml = _check_xml
