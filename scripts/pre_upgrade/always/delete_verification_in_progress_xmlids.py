import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'delete_verification_in_progress_xmlids.py' script for version %s", version)
    cr.execute(SQL("DELETE FROM ir_model_data WHERE module = 'verification in progress'"))
