"""Drop the customized dashboards when the ticket asks for it (parameter ``borrar_vistas_de_tablero``).

Only when there are fewer than 10: more than that is not a leftover, and support has to look.

Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 512.
FIRST_TARGET_VERSION = 20
MAX_VIEWS = 10


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, position="last", parameter="borrar_vistas_de_tablero"):
        return

    views = util.env(cr)["ir.ui.view.custom"].search([])
    if not views or len(views) >= MAX_VIEWS:
        _logger.info("%s customized dashboards, none dropped", len(views))
        return
    view_ids = views.ids
    try:
        with cr.savepoint():
            views.unlink()
    except Exception as e:
        log_message(cr, "Could not drop the customized dashboards %s: %s" % (view_ids, e), "warning")
        return
    _logger.info("Dropped %s customized dashboards: %s", len(view_ids), view_ids)
