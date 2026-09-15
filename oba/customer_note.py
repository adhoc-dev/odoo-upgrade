"""Customer notes emitted from an upgrade script.

The script states what the customer has to be told and keeps migrating: it does not know
where that is stored, nor who publishes it. The provider reads it once the upgrade is
over and publishes the note as it always did.

    from odoo.upgrade.oba import add_customer_note

    def migrate(cr, version):
        add_customer_note(cr, "valoracion-stock-accionables", {"rows": rows})

Replaces the ``ir.config_parameter`` ten notes use for this today. The parameter does not
say which run wrote it, so it survives a retry of the migration and breaks the next one
(T-126384); here the upsert by slug overwrites the stale value.

Public API: :func:`add_customer_note`. Everything else is internal.
"""

import json
import logging
import os
import re
import sys

from odoo.modules.migration import VERSION_RE

_logger = logging.getLogger(__name__)

TABLE = "oba_upgrade_customer_note"

# Written by hand on both sides, here and on the note, so keep it narrow.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_THIS_FILE = os.path.abspath(__file__)


def add_customer_note(cr, slug, values):
    """Store the values the customer note ``slug`` will show the customer.

    Idempotent: two runs of the same script overwrite the same row, so retrying the
    upgrade neither duplicates nor leaves stale values behind.

    :param cr: migration cursor, on the customer's database
    :param slug: identifies the note; lowercase, digits and hyphens
    :param values: variables the note's message renders, as a JSON-serializable dict
    :raises ValueError: malformed slug, values that are not a JSON-serializable dict, or
        a caller outside the upgrade path
    """
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise ValueError(
            "add_customer_note: the slug must be lowercase, digits and hyphens, got %r. "
            "Called from %s" % (slug, _caller_script())
        )
    if not isinstance(values, dict):
        raise ValueError(
            "add_customer_note(%r): values must be a dict, got %s. Called from %s"
            % (slug, type(values).__name__, _caller_script())
        )

    module = _caller_module()
    try:
        payload = json.dumps(values)
    except TypeError as exc:
        # psycopg would say "can't adapt type" and point at the query; the script built it.
        raise ValueError(
            "add_customer_note(%r): values must be JSON-serializable (%s). Called from %s"
            % (slug, exc, _caller_script())
        ) from exc

    _ensure_table(cr)
    cr.execute(
        """
        INSERT INTO {table} (slug, module, vals, created_at)
             VALUES (%s, %s, %s::jsonb, now() at time zone 'UTC')
        ON CONFLICT (slug) DO UPDATE
                SET module = EXCLUDED.module,
                    vals = EXCLUDED.vals,
                    created_at = EXCLUDED.created_at
        """.format(table=TABLE),
        (slug, module, payload),
    )
    _logger.info("Customer note %r: %s variables from %s", slug, len(values), module)


def _ensure_table(cr):
    """Create the table if missing, so the first caller cannot fail on ordering."""
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            slug varchar PRIMARY KEY,
            module varchar NOT NULL,
            vals jsonb NOT NULL,
            created_at timestamp NOT NULL
        )
        """.format(table=TABLE)
    )
    # The PK is what the upsert rests on, and it also spares us Odoo's test_ensure_has_pk
    # CRITICAL. The column is `vals` and not `values` because VALUES is reserved in SQL.


def _caller_script():
    """The file of the script that called, so errors say where to look."""
    frame = sys._getframe(1)
    while frame is not None and os.path.abspath(frame.f_code.co_filename) == _THIS_FILE:
        frame = frame.f_back
    return os.path.abspath(frame.f_code.co_filename) if frame is not None else "<unknown>"


def _caller_module():
    """The module of the calling script, taken from its ``<module>/<version>/`` path.

    Recorded beside the values so a row says which module wrote it. It is not what
    identifies the note -- the slug is, and a module can hold several scripts and several
    notes. Taken instead of asked for, and the version folder is validated with Odoo's own
    expression: if it does not match, the module we would return is anything at all.
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
    return module
