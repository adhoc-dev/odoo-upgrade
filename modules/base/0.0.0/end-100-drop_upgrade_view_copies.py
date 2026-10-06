"""Drop the inactive view copies that the Odoo upgrade creates for broken customizations.

They count as customizations and push the database over the limit of the plan. A failure is
reported and does not stop the -u, as the upgrade line did not stop the upgrade either.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.upgrade import util
from oba import log_message

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 884.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    views = util.env(cr)["ir.ui.view"].with_context(active_test=False).search(
        [("active", "=", False), ("name", "ilike", "(Copy created during upgrade)")]
    )
    if not views:
        return
    view_ids = views.ids
    try:
        with cr.savepoint():
            views.unlink()
    except Exception as e:
        log_message(cr, "Could not drop the view copies created by the upgrade %s: %s" % (view_ids, e), "warning")
        return
    _logger.info("Dropped %s view copies created by the upgrade: %s", len(view_ids), view_ids)
