"""Check again the views whose check ``pre-0-disable-check-views.py`` delayed.

With every module loaded, a view that still fails is not a transient error: the fixdb of the
postupgrade would stop the request on it. It goes to the request as a warning, with its
xmlid, so it can be fixed before the fixdb. Nothing is changed: the custom views that fail
are already archived by ``end-210-check_personalizations.py``.

In ``modules/base/0.0.0`` so it runs on every jump, after the other end scripts and before
``end-900``.
"""

import logging

from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not should_run(cr, version):
        return
    View = util.env(cr)["ir.ui.view"]
    delayed = getattr(type(View), "_upgrade_delayed_view_ids", set())
    if not delayed:
        return

    failing = []
    for view in View.search([("id", "in", list(delayed))]):
        try:
            with cr.savepoint():
                type(View)._upgrade_original_check_xml(view)
        except Exception as e:
            failing.append("%s (%s): %s" % (view.get_external_id()[view.id] or view.id, view.name, e))
    _logger.info("Checked again %s delayed views, %s still fail", len(delayed), len(failing))
    if failing:
        log_message(
            cr, "Vistas que siguen fallando después de actualizar:\n%s" % "\n".join(failing), "warning", module="base",
        )
