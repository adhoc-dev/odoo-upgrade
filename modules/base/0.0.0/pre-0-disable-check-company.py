"""Turn off the company check while the scripts run.

In ``modules/base/0.0.0`` so it runs on every jump from 20 on; until 19 each version folder
has its own copy.
"""

import logging

from odoo.models import BaseModel

from oba import should_run

_logger = logging.getLogger(__name__)


_original_check_company = BaseModel._check_company


def _check_company(self, fnames=None):
    """Patch _check_company to avoid any error when run scripts, we enable later"""
    try:
        _original_check_company
    except Exception as e:
        _logger.warning("incompatible companies. This is what we get:\n%s", e)


def migrate(cr, version):
    if not should_run(cr, version):
        return
    BaseModel._check_company = _check_company
