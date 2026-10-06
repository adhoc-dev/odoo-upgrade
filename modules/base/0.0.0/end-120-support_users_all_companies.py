"""Give the root and admin users every active company, with a root company as the default.

With branches the first company found can be a branch, so the default is taken among the
companies without a parent. Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.upgrade import util
from oba import log_message, request_context

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 1171.
FIRST_TARGET_VERSION = 20
USER_XMLIDS = ("base.user_root", "base.user_admin")


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if not request_context(cr).get("is_last_in_series", True):
        return

    env = util.env(cr)
    companies = env["res.company"].search([])
    default_company = env["res.company"].search([("parent_id", "=", False)], limit=1) or companies[:1]
    for xmlid in USER_XMLIDS:
        user = env.ref(xmlid, raise_if_not_found=False)
        if not user:
            log_message(cr, "User %s not found: its companies are not set" % xmlid, "warning")
            continue
        if user.company_ids == companies and user.company_id == default_company:
            continue
        try:
            with cr.savepoint():
                user.write({"company_ids": [(6, 0, companies.ids)], "company_id": default_company.id})
        except Exception as e:
            log_message(cr, "Could not set the companies of %s: %s" % (xmlid, e), "warning")
            continue
        _logger.info("%s now has companies %s, default %s", xmlid, companies.ids, default_company.id)
