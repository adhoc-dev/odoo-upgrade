"""The upgrade request a migration script runs for.

    from odoo.upgrade.oba import request_context

    def migrate(cr, version):
        context = request_context(cr)
        if not context.get("is_last_in_series", True):
            return

The runner of the ``-u`` (``odoo_obaupgrade.py`` of ``saas_provider_upgrade``) writes it to
a config parameter before the first script runs and drops it when the job ends. Keys:
``parameters``, ``from_version``, ``is_first_in_series`` and ``is_last_in_series``. Nothing
about the provider: what a script does there is solved by the controller, on the callback.
The target version is the running Odoo (``odoo.release``).

Outside a provider run (runbot, a local ``-u``) there is no parameter and the context is
empty: a script that needs it falls back to its default, or does nothing.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# The key the runner writes. The two sides cannot import each other, so it is spelled here
# again; a script reading a misspelled key would fall back to its default in silence.
PARAMETER = "saas_upgrade.request_context"


def request_context(cr):
    """The request context left by the runner, or ``{}`` when there is none.

    :param cr: migration cursor, on the customer's database
    """
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (PARAMETER,))
    row = cr.fetchone()
    if not row or not row[0]:
        return {}
    try:
        context = json.loads(row[0])
    except ValueError:
        _logger.warning("The upgrade request context is not JSON, ignored")
        return {}
    return context if isinstance(context, dict) else {}
