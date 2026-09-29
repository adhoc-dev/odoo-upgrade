import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'adjust_deprecated_assets.py' script for version %s", version)
    cr.execute("DELETE FROM ir_asset WHERE name like '%--view_id%' and name not like '%web_editor.%'")
    cr.execute("DELETE FROM ir_asset WHERE name like '%--view_id%' and bundle = 'web.assets_frontend'")
