"""Reload the terms of every active language, overwriting the ones in the database.

A failure is reported and does not stop the -u, as the upgrade line did not stop the upgrade
either.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 597.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION):
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
