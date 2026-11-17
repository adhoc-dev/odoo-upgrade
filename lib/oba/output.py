"""What a migration script has to say back to the upgrade request.

    from oba import create_record_provider, log_message, set_breaks, set_result

    def migrate(cr, version):
        log_message(cr, "Se desinstalaron 3 módulos", "warning", module="base")

The counterpart of ``log_message``, ``result`` and ``breaks`` of an upgrade line. A warning
or error carries its ``module``, from which the provider gets the product; ``info`` goes only
to the log of the process. Each other call leaves a row in ``saas_upgrade_output``; the runner
of the ``-u`` delivers the rows in its callback when the job ends and the provider records them
on the request. ``result`` is posted on the request and ``breaks`` stops it, both after the
``-u`` finishes: the script itself keeps running, and the last call of each wins.
``create_record_provider`` asks the provider to create a record, with the same contract as an
upgrade line (``saas_provider_upgrade/provider_records.py``).

Without the runner (runbot, a local ``-u``) there is no table and nobody to deliver to: the
message goes to the log of the process and nothing else happens.
"""

import json
import logging
import os
import sys
import uuid

_logger = logging.getLogger(__name__)

# The table the runner creates before the -u and reads when it ends. Spelled here again
# because the two sides cannot import each other.
TABLE = "saas_upgrade_output"
LOG_TYPES = ("info", "warning", "error")

# Values for the vals of create_record_provider: the provider replaces each one by the id of
# what the upgrade request has under that name.
UPGRADE_TICKET = {"$request": "upgrade_ticket"}
UPGRADE_PROJECT = {"$request": "upgrade_project"}
ASSIGNED_TECHNICIAN = {"$request": "assigned_technician"}
ASSIGNED_TECHNICIAN_PARTNER = {"$request": "assigned_technician_partner"}
BUGFIX_TEAM = {"$request": "bugfix_team"}
_REQUEST_MARKERS = (UPGRADE_TICKET, UPGRADE_PROJECT, ASSIGNED_TECHNICIAN, ASSIGNED_TECHNICIAN_PARTNER, BUGFIX_TEAM)

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


def create_record_provider(cr, model, vals, *, context=None, ref=None):
    """Ask the provider to create a record when the step reports back, once even if the callback is retried.

    Same arguments and handle as ``create_record_provider`` of an ``odoo_shell`` upgrade line. A
    malformed call or an unknown request marker fails here; the model is checked against the
    allowlist by the provider, which warns on the request if it rejects the call. The request
    markers (``UPGRADE_TICKET``, ``BUGFIX_TEAM``, ...) go as values of ``vals``::

        create_record_provider(cr, "helpdesk.ticket", {"name": "...", "parent_id": UPGRADE_TICKET})

    :param model: model to create in the provider
    :param vals: values for the create, a non-empty dict
    :param context: context for the create
    :param ref: key the provider skips a retried callback by; a uuid4 hex if omitted
    :return: ``{"ref", "model", "id": None, "deferred": True}``
    """
    if not model or not isinstance(model, str):
        raise ValueError("create_record_provider expects a model name (str) as first argument.")
    if not isinstance(vals, dict) or not vals:
        raise ValueError("create_record_provider expects a non-empty dict of values (vals).")
    if not all(isinstance(key, str) for key in vals):
        raise ValueError("create_record_provider expects field names (str) as keys of vals.")
    if context is not None and not isinstance(context, dict):
        raise ValueError("create_record_provider expects a dict as context, or None.")
    if context and not all(isinstance(key, str) for key in context):
        raise ValueError("create_record_provider expects key names (str) as keys of context.")
    if ref is not None and (not isinstance(ref, str) or not ref):
        raise ValueError("create_record_provider expects a non-empty str as ref, or None.")
    unknown = [
        value["$request"]
        for value in vals.values()
        if isinstance(value, dict) and set(value) == {"$request"} and value not in _REQUEST_MARKERS
    ]
    if unknown:
        raise ValueError(
            "create_record_provider does not know the request markers %s. Known: %s."
            % (", ".join(sorted(map(str, unknown))), ", ".join(marker["$request"] for marker in _REQUEST_MARKERS))
        )
    ref = ref or uuid.uuid4().hex
    payload = {"ref": ref, "model": model, "vals": vals, "context": context or {}}
    try:
        # jsonb rejects NaN, and \u0000 below
        dumped = json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("create_record_provider expects JSON-serializable vals and context: %s" % exc) from exc
    if "\\u0000" in dumped:
        raise ValueError("create_record_provider cannot send a NUL character: jsonb rejects it.")
    _write(cr, "provider_record", payload)
    return {"ref": ref, "model": model, "id": None, "deferred": True}


def _write(cr, kind, payload):
    payload["migration_script"] = _caller_script()
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (TABLE,))
    if not cr.fetchone():
        _logger.info(
            "No upgrade request to deliver to; %s from %s: %s",
            kind,
            payload["migration_script"],
            payload.get("message", payload),
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
