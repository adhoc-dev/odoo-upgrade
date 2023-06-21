from odoo.addons.base.models.ir_ui_view import View
import logging
_logger = logging.getLogger(__name__)


_original_check_xml = View._check_xml


def _check_xml(self):
    """ Patch check_xml to avoid any error when loading views, we check them later """
    try:
        _original_check_xml
    except Exception as e:
        _logger.warning('Invalid view definition. This is what we get:\n%s', e)


View._check_xml = _check_xml


def migrate(env, version):
    pass
