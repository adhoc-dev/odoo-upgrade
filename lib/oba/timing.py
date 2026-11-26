"""Log how long an upgrade script takes.

Odoo logs when a script starts but not when it ends, and the next line also counts the loading
of the module. Each script decorates its ``migrate``:

    from oba import timed

    @timed
    def migrate(cr, version):
        ...
"""

import functools
import logging
import os
import time

from .output import _REPO

_logger = logging.getLogger(__name__)


def timed(migrate):
    """Log how long ``migrate`` took, also when it fails."""
    path = os.path.abspath(migrate.__code__.co_filename)
    # Relative to the repo, as log_message names the script; a script from elsewhere by its name
    script = os.path.relpath(path, _REPO) if path.startswith(_REPO + os.sep) else os.path.basename(path)

    @functools.wraps(migrate)
    def wrapper(cr, version):
        start = time.monotonic()
        try:
            return migrate(cr, version)
        finally:
            _logger.info("%s took %.2fs", script, time.monotonic() - start)

    return wrapper
