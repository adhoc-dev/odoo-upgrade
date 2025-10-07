import logging

from odoo.tools import SQL
from odoo.upgrade import util
from odoo.upgrade.util.modules import _trigger_auto_discovery

_logger = logging.getLogger(__name__)

MERGE_MODULES = []
RENAMED_MODULES = []
RENAMED_XMLIDS = []


def migrate(cr, version):
    _logger.info("Running 'merge_and_renames' script for version %s", version)
    _trigger_auto_discovery(cr)
    for old, into in MERGE_MODULES:
        util.merge_module(cr, old, into, update_dependers=False)
    for old, into in RENAMED_MODULES:
        util.rename_module(cr, old, into)
    for old, into in RENAMED_XMLIDS:
        util.rename_xmlid(cr, old, into)

    version = float(".".join(version.split(".")[0:2]))  # Version is str, ex. '18.0.1.3'
    version_string = f"{version - 1}.0.0"
    cr.execute(
        SQL(
            """
        UPDATE ir_module_module
        SET latest_version = %(version)s
        WHERE latest_version IS NULL AND state = 'installed'
        """,
            version=version_string,
        )
    )
