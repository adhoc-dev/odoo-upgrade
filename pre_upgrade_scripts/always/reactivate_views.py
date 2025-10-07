import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'reactivate_views.py' script for version %s", version)
    cr.execute(
        SQL(
            "SELECT id FROM ir_ui_view where active = True"
        )
    )
    res = cr.fetchall()
    ids = [x[0] for x in res]
    if ids:
        cr.execute(
            SQL(
                "UPDATE ir_ui_view SET active = True WHERE id IN %(ids)s",
                ids=tuple(ids)
            )
        )
