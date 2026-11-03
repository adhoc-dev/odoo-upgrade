"""The pre-migration of saas_provider 20.0 that removes the shared postgres.

The script only calls ``util``, so the tests replace it and check which calls run: what
they do is upgrade-util's. They need no Odoo running, only importable, in the target
version (20.0 or later).

    /home/odoo/venv/bin/python modules/saas_provider/tests/test_shared_postgres.py

``ODOO_PATH`` points them at another checkout.
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import MagicMock, call, patch

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPT = os.path.join(REPO, "modules", "saas_provider", "20.0.1.0.0", "pre-migration.py")

try:
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("saas_provider_pre_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()


class SharedPostgresCase(unittest.TestCase):
    def _migrate(self):
        with patch.object(script, "util") as util:
            script.migrate(self.cr, "19.0.1.0.0")
        return util

    def setUp(self):
        self.cr = MagicMock()

    def test_the_mode_goes(self):
        """Nothing defines the postgres mode in 20: the field and its related one go."""
        util = self._migrate()
        util.remove_field.assert_any_call(self.cr, "saas.environment", "postgres_mode")
        util.remove_field.assert_any_call(self.cr, "saas.database", "environment_postgres_mode")

    def test_servers_go_with_their_history(self):
        """The two server models, the fields that point to them and the cron of the servers go."""
        util = self._migrate()
        util.remove_record.assert_called_once_with(self.cr, "saas_provider.ir_cron_remove_hanging_databases")
        util.remove_field.assert_any_call(self.cr, "saas.database", "postgres_server_id")
        util.remove_field.assert_any_call(self.cr, "saas.environment", "postgres_server_ids")
        util.remove_model.assert_has_calls(
            [call(self.cr, "saas.environment.postgres.server"), call(self.cr, "saas.postgres.server")]
        )

    def test_fields_go_before_their_models(self):
        """The fields that point to the server models go first, so remove_model finds nothing left."""
        util = self._migrate()
        names = [c[0] for c in util.method_calls]
        last_field = max(i for i, name in enumerate(names) if name == "remove_field")
        self.assertLess(last_field, names.index("remove_model"))

    def test_the_tunnel_parameter_goes(self):
        """The tunnel parameter is a system parameter, not a field: remove_model does not drop it."""
        self._migrate()
        self.cr.execute.assert_called_once_with(
            "DELETE FROM ir_config_parameter WHERE key = %s", ["saas_postgres_server.use_tunnel"]
        )


if __name__ == "__main__":
    unittest.main()
