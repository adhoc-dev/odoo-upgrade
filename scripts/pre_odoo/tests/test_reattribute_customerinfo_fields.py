"""The xmlid reattribution of ``scripts/pre_odoo/190_200/020-reattribute_customerinfo_fields.py``.

Same harness as ``test_always_upgrade_lines``: an own Postgres database, no Odoo running.

    /home/odoo/venv/bin/python scripts/pre_odoo/tests/test_reattribute_customerinfo_fields.py
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCRIPT = os.path.join(REPO, "scripts", "pre_odoo", "190_200", "020-reattribute_customerinfo_fields.py")

sys.path.insert(0, HERE)

from test_always_upgrade_lines import OldDatabaseCase  # noqa: E402


def _load_script():
    spec = importlib.util.spec_from_file_location("s020_reattribute_customerinfo_fields", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reattribute = _load_script()

# (campo, modulo de Odoo que el ORM deja como dueno del xmlid)
FIELDS = [
    ("purchase_requisition_line_id", "purchase_requisition"),
    ("purchase_requisition_id", "purchase_requisition"),
    ("last_purchase_date", "purchase_stock"),
    ("show_set_supplier_button", "purchase_stock"),
    ("is_subcontractor", "mrp_subcontracting"),
]


class TestReattributeCustomerinfoFields(OldDatabaseCase):
    TABLES = """
        CREATE TABLE ir_model_fields (id serial PRIMARY KEY, model varchar, name varchar);
    """

    def setUp(self):
        super().setUp()
        self.install("product_customerinfo", "purchase_requisition", "purchase_stock", "mrp_subcontracting")
        for index, (field, module) in enumerate(FIELDS, start=1):
            self.cr.execute(
                "INSERT INTO ir_model_fields (id, model, name) VALUES (%s, 'product.customerinfo', %s)",
                (index, field),
            )
            self.xmlid(module, "field_product_customerinfo__%s" % field, "ir.model.fields", index)

    def owners(self):
        return self.rows("SELECT name, module FROM ir_model_data ORDER BY id")

    def test_reattributes_the_five_fields_and_reports_it(self):
        reattribute.migrate(self.cr, "19.0")
        self.assertEqual(
            self.owners(),
            [("field_product_customerinfo__%s" % field, "product_customerinfo") for field, _module in FIELDS],
        )
        ((type_, message),) = self.logs()
        self.assertEqual(type_, "info")
        for field, module in FIELDS:
            self.assertIn("product.customerinfo.%s (%s)" % (field, module), message)

    def test_second_run_changes_nothing(self):
        reattribute.migrate(self.cr, "19.0")
        before = self.owners()
        reattribute.migrate(self.cr, "19.0")
        self.assertEqual(self.owners(), before)
        self.assertEqual(len(self.logs()), 1)

    def test_nothing_without_the_module(self):
        self.cr.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = 'product_customerinfo'")
        reattribute.migrate(self.cr, "19.0")
        self.assertEqual({module for _name, module in self.owners()} & {"product_customerinfo"}, set())
        self.assertEqual(self.logs(), [])

    def test_nothing_on_an_upgrade_to_19(self):
        self.write_context(from_version="18.0", to_version="19.0")
        reattribute.migrate(self.cr, "18.0")
        self.assertEqual({module for _name, module in self.owners()} & {"product_customerinfo"}, set())

    def test_runs_without_a_request_context(self):
        reattribute.migrate(self.cr, "19.0")
        self.assertEqual({module for _name, module in self.owners()}, {"product_customerinfo"})

    def test_keeps_one_xmlid_when_the_module_already_claimed_the_field(self):
        # Al actualizar el modulo, Odoo ya dejo uno suyo: moverlo violaria el indice unico.
        self.xmlid("product_customerinfo", "field_product_customerinfo__is_subcontractor", "ir.model.fields", 5)
        reattribute.migrate(self.cr, "19.0")
        self.assertEqual(
            self.rows(
                "SELECT module FROM ir_model_data WHERE name = 'field_product_customerinfo__is_subcontractor'"
            ),
            [("product_customerinfo",)],
        )

    def test_leaves_an_orphan_xmlid_alone(self):
        # Un huerfano (modulo que no esta en ir_module_module) no lo reclama nadie.
        self.xmlid("__export__", "field_product_customerinfo__is_subcontractor", "ir.model.fields", 5)
        reattribute.migrate(self.cr, "19.0")
        self.assertIn(
            ("__export__",),
            self.rows("SELECT module FROM ir_model_data WHERE name = 'field_product_customerinfo__is_subcontractor'"),
        )

    def test_does_not_touch_an_xmlid_of_another_field_with_the_same_name(self):
        self.xmlid("sale", "field_product_customerinfo__is_subcontractor", "ir.model.fields", 99)
        reattribute.migrate(self.cr, "19.0")
        self.assertIn(
            ("sale", 99),
            self.rows(
                "SELECT module, res_id FROM ir_model_data WHERE name = 'field_product_customerinfo__is_subcontractor'"
            ),
        )


if __name__ == "__main__":
    unittest.main()
