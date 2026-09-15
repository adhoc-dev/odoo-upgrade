"""Customer notes emitted from an upgrade script.

    from odoo.upgrade.oba import add_customer_note

    def migrate(cr, version):
        add_customer_note(cr, "valoracion-stock-accionables", {"rows": rows})

The script says what the customer has to be told and keeps migrating. The provider reads
the values after the upgrade and publishes the note.

Public API: :func:`add_customer_note`. Everything else is internal.
"""

import json
import keyword
import logging
import os
import re
import sys

from odoo.modules.migration import VERSION_RE

_logger = logging.getLogger(__name__)

TABLE = "oba_upgrade_customer_note"

# The same slug is written by hand on the note's upgrade line, so it needs one spelling.
# Starting with a letter buys nothing today; it is kept in case the slug ever names something.
SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

_THIS_FILE = os.path.abspath(__file__)


def add_customer_note(cr, slug, values):
    """Store the values the customer note ``slug`` will show the customer.

    Two runs of the same script overwrite the same row, so retrying the upgrade does not
    duplicate.

    :param cr: migration cursor, on the customer's database
    :param slug: identifies the note; lowercase, digits and hyphens
    :param values: what the message renders, as a JSON-serializable dict. Its keys are the
        names the message reads.
    :raises ValueError: bad slug, bad values, a caller outside the upgrade path, or a slug
        another script already took
    """
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise ValueError(
            "add_customer_note: the slug must start with a letter and hold only lowercase, "
            "digits and hyphens, got %r. Called from %s" % (slug, _caller_script())
        )
    if not isinstance(values, dict):
        raise ValueError(
            "add_customer_note(%r): values must be a dict, got %s. Called from %s"
            % (slug, type(values).__name__, _caller_script())
        )
    for key in values:
        # The message reads these keys by name, so one that is not a valid name cannot be
        # named there and nothing renders.
        if not isinstance(key, str) or not key.isidentifier() or keyword.iskeyword(key):
            raise ValueError(
                "add_customer_note(%r): %r cannot be a variable name, and the message reads "
                "these keys by name. Called from %s" % (slug, key, _caller_script())
            )

    script, module = _caller_location()
    try:
        payload = json.dumps(values)
    except TypeError as exc:
        # psycopg would say "can't adapt type" and point at the query; the script built it.
        raise ValueError(
            "add_customer_note(%r): values must be JSON-serializable (%s). Called from %s"
            % (slug, exc, _caller_script())
        ) from exc

    _ensure_table(cr)
    # The same script writing again is a retry. A different one means two scripts picked the
    # same slug, and which one survived would be up to the module graph.
    cr.execute("SELECT script FROM {table} WHERE slug = %s".format(table=TABLE), (slug,))
    taken = cr.fetchone()
    if taken and taken[0] != script:
        raise ValueError(
            "add_customer_note(%r): the slug is already taken by %s. Called from %s. "
            "Two scripts cannot feed one customer note: pick a different slug."
            % (slug, taken[0], script)
        )

    cr.execute(
        """
        INSERT INTO {table} (slug, module, script, vals, created_at)
             VALUES (%s, %s, %s, %s::jsonb, now() at time zone 'UTC')
        ON CONFLICT (slug) DO UPDATE
                SET vals = EXCLUDED.vals,
                    created_at = EXCLUDED.created_at
        """.format(table=TABLE),
        (slug, module, script, payload),
    )
    _logger.info("Customer note %r: %s variables from %s", slug, len(values), script)


def _ensure_table(cr):
    """Create the table if missing, so the first caller cannot fail on ordering."""
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            slug varchar PRIMARY KEY,
            module varchar NOT NULL,
            script varchar NOT NULL,
            vals jsonb NOT NULL,
            created_at timestamp NOT NULL
        )
        """.format(table=TABLE)
    )
    # The primary key is what the upsert rests on, and it keeps test_ensure_has_pk quiet.
    # The column is `vals` and not `values` because VALUES is reserved in SQL.


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
