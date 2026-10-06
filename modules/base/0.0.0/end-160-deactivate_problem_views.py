"""Deactivate the views that the ticket lists in the parameter ``deactivate_views_ids``.

Support fills the parameter with the views that break the upgrade of a customer. Each one is
renamed to say why it is inactive. By SQL, so a broken view is not validated on the write.

Only on the last jump of the request. Idempotent: a view already renamed keeps its name.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo import release
from oba import log_message, request_context, should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 371.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, position="last", parameter="deactivate_views_ids"):
        return

    parameter = request_context(cr)["parameters"]["deactivate_views_ids"]
    # The upgrade line also took a single id. A non-integer entry cannot be an id: it is reported.
    if not isinstance(parameter, (list, tuple)):
        parameter = [parameter]
    view_ids = [view_id for view_id in parameter if isinstance(view_id, int) and not isinstance(view_id, bool)]
    discarded = [view_id for view_id in parameter if view_id not in view_ids]
    if discarded:
        log_message(cr, "deactivate_views_ids: ignored values that are not view ids: %s" % discarded, "warning")
    if not view_ids:
        return

    suffix = " (Desactivada en actualizacion a %s por traer problemas)" % release.major_version
    cr.execute(
        """
        UPDATE ir_ui_view
           SET active = false,
               name = CASE WHEN right(name, length(%s)) = %s THEN name ELSE name || %s END
         WHERE id = ANY(%s)
     RETURNING id
        """,
        (suffix, suffix, suffix, view_ids),
    )
    deactivated = sorted(row[0] for row in cr.fetchall())
    if deactivated:
        _logger.info("Views deactivated by the ticket parameter: %s", deactivated)
