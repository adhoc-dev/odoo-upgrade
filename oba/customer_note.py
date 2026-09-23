"""Customer notes emitted from an upgrade script.

    from odoo.upgrade.oba import add_customer_note

    def migrate(cr, version):
        add_customer_note(cr, {"escenario_b_rows": rows})

The script says what the customer has to be told and keeps migrating. The provider reads
the values the message names and publishes the note.

The table outlives the upgrade on purpose: it is the record of what the customer was told,
and what a note is rebuilt from if its content changes.

Public API: :func:`add_customer_note`. Everything else is internal.
"""

import json
import keyword
import logging
import os
import sys

from odoo.modules.migration import VERSION_RE

_logger = logging.getLogger(__name__)

TABLE = "oba_upgrade_customer_note"

_INSERT = """
    INSERT INTO {table} (key, value, module, script, created_at)
         VALUES (%s, %s::jsonb, %s, %s, now() at time zone 'UTC')
    ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                module = EXCLUDED.module,
                script = EXCLUDED.script,
                created_at = EXCLUDED.created_at
""".format(table=TABLE)

_THIS_FILE = os.path.abspath(__file__)


def add_customer_note(cr, values):
    """Store the values a customer note will show the customer, one row per name.

    The message reads them by the names it renders, so nothing here says which note they
    belong to. Two runs of the same script overwrite the same rows, and so does another
    script that writes the same name: the last one wins.

    :param cr: migration cursor, on the customer's database
    :param values: what the message renders, as a JSON-serializable dict. Its keys are the
        names the message reads.
    :raises ValueError: bad values, or a caller outside the upgrade path
    """
    caller = _caller_script()
    if not isinstance(values, dict):
        raise ValueError(
            "add_customer_note: values must be a dict, got %s. Called from %s"
            % (type(values).__name__, caller)
        )

    script, module = _caller_location()
    rows = []
    for key, value in values.items():
        # The message reads these keys by name, so one that is not a valid name cannot be
        # named there and nothing renders.
        if not isinstance(key, str) or not key.isidentifier() or keyword.iskeyword(key):
            raise ValueError(
                "add_customer_note: %r cannot be a variable name, and the message reads "
                "these keys by name. Called from %s" % (key, caller)
            )
        try:
            # allow_nan=False, because json.dumps writes a NaN as a bare token that jsonb
            # rejects: the error would point at the query, and the script built the value.
            rows.append((key, json.dumps(value, allow_nan=False), module, script))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "add_customer_note: %r must be JSON-serializable (%s). Called from %s"
                % (key, exc, caller)
            ) from exc

    if not rows:
        return

    _ensure_table(cr)
    for row in rows:
        cr.execute(_INSERT, row)
    _logger.info("Customer note values from %s: %s", script, ", ".join(sorted(values)))


def _ensure_table(cr):
    """Create the table if missing, so the first caller cannot fail on ordering."""
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            key varchar PRIMARY KEY,
            value jsonb NOT NULL,
            module varchar NOT NULL,
            script varchar NOT NULL,
            created_at timestamp NOT NULL
        )
        """.format(table=TABLE)
    )
    # The primary key is what the upsert rests on, and it keeps test_ensure_has_pk quiet.


def _caller_script():
    """The file of the script that called, so errors say where to look."""
    frame = sys._getframe(1)
    while frame is not None and os.path.abspath(frame.f_code.co_filename) == _THIS_FILE:
        frame = frame.f_back
    return os.path.abspath(frame.f_code.co_filename) if frame is not None else "<unknown>"


def _caller_location():
    """The calling script as ``("<module>/<version>/<script>.py", module)``.

    Both come from the path: in the upgrade path a script always lives in
    ``<module>/<version>/``. The version folder is checked with Odoo's own expression,
    because outside that layout the module would be anything.

    The path is relative so it compares equal between two runs of the same script; the
    absolute one carries the checkout it ran from.
    """
    script = _caller_script()
    version_dir = os.path.dirname(script)
    module = os.path.basename(os.path.dirname(version_dir))
    version = os.path.basename(version_dir)
    if not VERSION_RE.match(version):
        raise ValueError(
            "add_customer_note can only be called from an upgrade-path script, which lives in "
            "<module>/<version>/. %s is in %r, which is not a version folder." % (script, version)
        )
    return "%s/%s/%s" % (module, version, os.path.basename(script)), module
