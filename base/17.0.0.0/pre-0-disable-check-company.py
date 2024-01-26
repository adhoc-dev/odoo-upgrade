from odoo.models import BaseModel
import logging
_logger = logging.getLogger(__name__)


_original_check_company = BaseModel._check_company


def _check_company(self, fnames=None):
    """ Patch chec_check_company to avoid any error when run scripts, we enable later """
    try:
        _original_check_company
    except Exception as e:
        _logger.warning('incompatible companies. This is what we get:\n%s', e)


BaseModel._check_company = _check_company


def migrate(env, version):
    pass
