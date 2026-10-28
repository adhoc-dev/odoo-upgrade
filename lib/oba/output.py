"""What a migration script has to say back to the upgrade request.

    from oba import log_message, set_breaks, set_result

    def migrate(cr, version):
        log_message(cr, "Se desinstalaron 3 módulos", "warning", module="base")

The counterpart of ``log_message``, ``result`` and ``breaks`` of an upgrade line. A warning
or error carries its ``module``, from which the provider gets the product; ``info`` goes only
to the log of the process. Each other call leaves a row in ``saas_upgrade_output``; the runner
of the ``-u`` delivers the rows in its callback when the job ends and the provider records them
on the request. ``result`` is posted on the request and ``breaks`` stops it, both after the
``-u`` finishes: the script itself keeps running, and the last call of each wins.

Without the runner (runbot, a local ``-u``) there is no table and nobody to deliver to: the
message goes to the log of the process and nothing else happens.
"""

import json
import logging
import os
import sys

_logger = logging.getLogger(__name__)

# The table the runner creates before the -u and reads when it ends. Spelled here again
# because the two sides cannot import each other.
TABLE = "saas_upgrade_output"
LOG_TYPES = ("info", "warning", "error")

_THIS_FILE = os.path.abspath(__file__)
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(_THIS_FILE)))


def log_message(cr, message, type="info", module=None):
    """Warnings and errors reach the request with their module; ``info`` only the process log.

    :param cr: migration cursor, on the customer's database
    :param message: what to say
    :param type: ``info``, ``warning`` or ``error``
    :param module: technical name of the module the message is about
    """
    if type not in LOG_TYPES:
        raise ValueError("log_message: type must be one of %s, got %r" % (LOG_TYPES, type))
    if type == "info":
        _logger.info("%s: %s", _caller_script(), message)
        return
    payload = {"message": message, "type": type}
    if module is not None:
        payload["module"] = module
    _write(cr, "log", payload)


def set_result(cr, message):
    """The result the provider posts on the request when the ``-u`` ends."""
    _write(cr, "result", {"message": message})


def set_breaks(cr, message):
    """Stop the request when the ``-u`` ends, with this message as the reason."""
    _write(cr, "breaks", {"message": message})


def _write(cr, kind, payload):
    payload["migration_script"] = _caller_script()
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (TABLE,))
    if not cr.fetchone():
        _logger.info(
            "No upgrade request to deliver to; %s from %s: %s", kind, payload["migration_script"], payload["message"]
        )
        return
    cr.execute(
        "INSERT INTO {table} (kind, payload) VALUES (%s, %s::jsonb)".format(table=TABLE),
        (kind, json.dumps(payload)),
    )


def _caller_script():
    """The script that called, relative to the repo, so the entry says where it came from."""
    frame = sys._getframe(1)
    while frame is not None and os.path.abspath(frame.f_code.co_filename) == _THIS_FILE:
        frame = frame.f_back
    if frame is None:
        return "<unknown>"
    path = os.path.abspath(frame.f_code.co_filename)
    if path.startswith(_REPO + os.sep):
        return os.path.relpath(path, _REPO)
    return os.path.basename(path)
