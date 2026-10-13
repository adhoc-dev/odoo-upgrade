"""The module renames of ``scripts/pre_odoo/180_190/020-module_renames.py``, by position in the series.

Same harness as ``test_always_upgrade_lines``: an own Postgres database, no Odoo running.

    /home/odoo/venv/bin/python scripts/pre_odoo/tests/test_module_renames.py
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(REPO, "scripts", "pre_odoo", "180_190", "020-module_renames.py")

sys.path.insert(0, HERE)

from test_always_upgrade_lines import OldDatabaseCase  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location("s020_module_renames", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renames = _load_script()


class TestModuleRenames(OldDatabaseCase):
    TABLES = """
        CREATE TABLE ir_module_module_dependency (id serial PRIMARY KEY, module_id integer, name varchar);
    """

    def setUp(self):
        super().setUp()
        self.install("l10n_uy_edi_stock")
        self.xmlid("base", "module_l10n_uy_edi_stock", "ir.module.module", 1)
        self.xmlid("l10n_uy_edi_stock", "view_picking_form", "ir.ui.view", 10)
        self.cr.execute("INSERT INTO ir_module_module_dependency (module_id, name) VALUES (2, 'l10n_uy_edi_stock')")

    def modules(self):
        return sorted(name for (name,) in self.rows("SELECT name FROM ir_module_module"))

    def test_renames_on_the_first_request_of_the_series(self):
        self.write_context(from_version="18.0", to_version="19.0", is_first_in_series=True)
        renames.migrate(self.cr, "18.0")
        self.assertEqual(self.modules(), ["l10n_uy_edi_stock_custom"])
        self.assertEqual(
            self.rows("SELECT module, name FROM ir_model_data ORDER BY id"),
            [("base", "module_l10n_uy_edi_stock_custom"), ("l10n_uy_edi_stock_custom", "view_picking_form")],
        )
        self.assertEqual(self.rows("SELECT name FROM ir_module_module_dependency"), [("l10n_uy_edi_stock_custom",)])

    def test_renames_without_a_request_context(self):
        renames.migrate(self.cr, "18.0")
        self.assertEqual(self.modules(), ["l10n_uy_edi_stock_custom"])

    def test_skips_a_request_that_follows_another(self):
        # The hop before already renamed it, by this script or by Odoo, and the new
        # auto-discovery registered the real name again: both rows are there.
        self.install("l10n_uy_edi_stock_custom")
        self.write_context(from_version="18.0", to_version="19.0", is_first_in_series=False)
        renames.migrate(self.cr, "18.0")
        self.assertEqual(self.modules(), ["l10n_uy_edi_stock", "l10n_uy_edi_stock_custom"])
        self.assertEqual(
            self.rows("SELECT module, name FROM ir_model_data ORDER BY id"),
            [("base", "module_l10n_uy_edi_stock"), ("l10n_uy_edi_stock", "view_picking_form")],
        )


if __name__ == "__main__":
    unittest.main()
