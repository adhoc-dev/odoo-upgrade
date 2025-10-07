import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'update_base_module_version.py' script for version %s", version)
    to_version = ".".join(version.split(".")[0:2])  # Version is str, ex. '18.0.1.3'
    from_version = f"{float(to_version) - 1}.0.0"
    cr.execute(SQL(
        """
        UPDATE ir_module_module set latest_version = %(from_version)s
        WHERE latest_version like %(to_version)s
        """,
        from_version=from_version,
        to_version=to_version
    ))

