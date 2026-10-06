"""Reload the terms of every active language, overwriting the ones in the database.

A failure is reported and does not stop the -u, as the upgrade line did not stop the upgrade
either.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import re

from odoo import release
from odoo.upgrade import util
from oba import log_message

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 597.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    env = util.env(cr)
    langs = env["res.lang"].search([])
    try:
        with cr.savepoint():
            env["base.language.install"].create({"lang_ids": [(6, 0, langs.ids)], "overwrite": True}).lang_install()
    except Exception as e:
        log_message(cr, "Could not reload the translations of %s: %s" % (langs.mapped("code"), e), "warning")
        return
    _logger.info("Translations reloaded for %s", langs.mapped("code"))
