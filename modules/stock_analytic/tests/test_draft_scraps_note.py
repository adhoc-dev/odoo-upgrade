"""The draft scraps that stock_analytic reports in the jump to 20, both halves end to end.

The pre-odoo backs them up on a 19 schema; the post-migration reads the backup and fills the
customer note data. The test creates and drops its own Postgres database with the tables the
scripts touch, so it needs no Odoo running, only an importable ``odoo.upgrade``.

    /home/odoo/venv/bin/python modules/stock_analytic/tests/test_draft_scraps_note.py

``ODOO_PATH`` and ``UPGRADE_TEST_DB`` point it at another checkout or another database.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_stock_analytic_draft_scraps_test")
PRE_ODOO = os.path.join(REPO, "scripts", "pre_odoo", "190_200", "030-stock_analytic_draft_scraps_backup.py")
POST = os.path.join(REPO, "modules", "stock_analytic", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from odoo.tools import SQL  # noqa: E402

from oba.customer_note import TABLE as NOTES  # noqa: E402
from oba.request_context import PARAMETER  # noqa: E402


class Cursor:
    """A psycopg2 cursor that takes ``odoo.tools.SQL``, the way Odoo's own cursor does."""

    def __init__(self, cr):
        self._cr = cr

    def execute(self, query, params=None):
        if isinstance(query, SQL):
            query, params, __ = query._sql_tuple
        return self._cr.execute(query, params)

    def __getattr__(self, name):
        return getattr(self._cr, name)


def _load(path, name):
    """Load a script by path: neither folder is a package and the names have a dash."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pre_odoo = _load(PRE_ODOO, "s030_stock_analytic_draft_scraps_backup")
post = _load(POST, "stock_analytic_post_migration")

# What the scripts read of a 19 database, and the bookkeeping oba reads on both sides.
SCHEMA = """
    CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
    CREATE TABLE ir_config_parameter (key varchar PRIMARY KEY, value text);
    CREATE TABLE res_partner (id serial PRIMARY KEY, lang varchar);
    CREATE TABLE res_company (id serial PRIMARY KEY, partner_id integer REFERENCES res_partner (id));
    CREATE TABLE product_template (id serial PRIMARY KEY, name jsonb);
    CREATE TABLE product_product (
        id serial PRIMARY KEY,
        product_tmpl_id integer REFERENCES product_template (id),
        default_code varchar
    );
    CREATE TABLE uom_uom (id serial PRIMARY KEY, name jsonb);
    CREATE TABLE account_analytic_account (id serial PRIMARY KEY, name jsonb);
    CREATE TABLE stock_scrap (
        id serial PRIMARY KEY,
        company_id integer REFERENCES res_company (id),
        product_id integer REFERENCES product_product (id),
        product_uom_id integer REFERENCES uom_uom (id),
        scrap_qty double precision,
        state varchar,
        create_date timestamp,
        analytic_distribution jsonb
    );
"""


class DraftScrapsCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        # UTF8 from template0: a template1 in SQL_ASCII cannot take the names' accents
        subprocess.run(["createdb", "-E", "UTF8", "-T", "template0", TEST_DB], check=True)
        cls.conn = psycopg2.connect(dbname=TEST_DB)
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = Cursor(self.conn.cursor())
        self.cr.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        self.cr.execute(SCHEMA)
        self.install("stock_analytic")
        self.cr.execute("INSERT INTO res_partner (lang) VALUES ('es_AR') RETURNING id")
        self.cr.execute("INSERT INTO res_company (partner_id) VALUES (%s) RETURNING id", (self.cr.fetchone()[0],))
        self.company = self.cr.fetchone()[0]
        self.product = self.product_("Tornillo", default_code="T-01")
        self.uom = self.uom_("Units", es_AR="Unidades")
        self.account = self.account_("Obra Norte")

    def install(self, *modules):
        for name in modules:
            self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, 'installed')", (name,))

    def write_context(self, **values):
        context = {"from_version": "19.0", "to_version": "20.0", "is_first_in_series": True, "is_last_in_series": True}
        context.update(values)
        self.cr.execute(
            "INSERT INTO ir_config_parameter (key, value) VALUES (%s, %s)", (PARAMETER, json.dumps(context))
        )

    def product_(self, name, default_code=None):
        self.cr.execute("INSERT INTO product_template (name) VALUES (%s) RETURNING id", (json.dumps({"en_US": name}),))
        self.cr.execute(
            "INSERT INTO product_product (product_tmpl_id, default_code) VALUES (%s, %s) RETURNING id",
            (self.cr.fetchone()[0], default_code),
        )
        return self.cr.fetchone()[0]

    def uom_(self, name, **translations):
        self.cr.execute(
            "INSERT INTO uom_uom (name) VALUES (%s) RETURNING id", (json.dumps({"en_US": name, **translations}),)
        )
        return self.cr.fetchone()[0]

    def account_(self, name, lang="en_US"):
        self.cr.execute(
            "INSERT INTO account_analytic_account (name) VALUES (%s) RETURNING id", (json.dumps({lang: name}),)
        )
        return self.cr.fetchone()[0]

    def scrap(self, distribution, state="draft", qty=2.0, date="2026-11-20 10:00:00", product=None):
        self.cr.execute(
            "INSERT INTO stock_scrap (company_id, product_id, product_uom_id, scrap_qty, state, create_date, "
            "analytic_distribution) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                self.company,
                product or self.product,
                self.uom,
                qty,
                state,
                date,
                json.dumps(distribution) if distribution is not None else None,
            ),
        )
        return self.cr.fetchone()[0]

    def jump(self):
        """The pre-odoo on the old database, then the post-migration on the new one.

        Same database for both: the pass to Odoo keeps the _bu, and the post only reads it.
        """
        pre_odoo.migrate(self.cr, "19.0.1.0.0")
        post.migrate(self.cr, "19.0.1.0.0")

    def notes(self):
        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (NOTES,))
        if not self.cr.fetchone():
            return {}
        self.cr.execute("SELECT key, value FROM %s" % NOTES)
        return dict(self.cr.fetchall())


class TestWhatIsReported(DraftScrapsCase):
    def test_draft_scrap_with_analytic_is_listed(self):
        """The case of the note: draft, with a distribution that 20 has nowhere to keep."""
        self.scrap({str(self.account): 100})

        self.jump()

        notes = self.notes()
        self.assertEqual(notes["scraps_borrador_count"], 1)
        self.assertEqual(
            notes["scraps_borrador"],
            [
                {
                    "fecha": "2026-11-20",
                    "producto": "[T-01] Tornillo",
                    "cantidad": 2.0,
                    "unidad": "Unidades",
                    "cuenta_analitica": "Obra Norte",
                }
            ],
        )

    def test_validated_scrap_is_not_listed(self):
        """Its distribution already travels on the stock move: nothing was lost."""
        self.scrap({str(self.account): 100}, state="done")

        self.jump()

        self.assertEqual(self.notes()["scraps_borrador_count"], 0)

    def test_draft_scrap_without_analytic_is_not_listed(self):
        """Nothing to load again: a null and an empty distribution are the same to the customer."""
        self.scrap(None)
        self.scrap({})

        self.jump()

        self.assertEqual(self.notes()["scraps_borrador_count"], 0)

    def test_split_and_combined_distribution_reads(self):
        """Percentages other than 100 show, and a line that combines plans joins its accounts."""
        other = self.account_("Mantenimiento", lang="es_AR")
        self.scrap({str(self.account): 60, "%s,%s" % (self.account, other): 40.5})

        self.jump()

        self.assertEqual(
            self.notes()["scraps_borrador"][0]["cuenta_analitica"],
            "Obra Norte (60 %), Obra Norte / Mantenimiento (40,5 %)",
        )

    def test_product_without_code_has_no_brackets(self):
        self.scrap({str(self.account): 100}, product=self.product_("Arandela"))

        self.jump()

        self.assertEqual(self.notes()["scraps_borrador"][0]["producto"], "Arandela")

    def test_every_scrap_is_listed_and_counted(self):
        """The note asks to fix each listed scrap, so the list is never cut: it matches the count."""
        for _ in range(55):
            self.scrap({str(self.account): 100}, date="2026-01-01 00:00:00")

        self.jump()

        notes = self.notes()
        self.assertEqual(notes["scraps_borrador_count"], 55)
        self.assertEqual(len(notes["scraps_borrador"]), 55)


class TestWhenToEmit(DraftScrapsCase):
    def test_nothing_to_report_still_emits(self):
        """The backup was there, so "nothing was lost" is a result the message may say."""
        self.jump()

        self.assertEqual(self.notes(), {"scraps_borrador_count": 0, "scraps_borrador": []})

    def test_module_not_installed_backs_up_nothing_and_post_emits_nothing(self):
        """Without stock_analytic no scrap had a distribution to lose. A zero would read as
        "we checked and you are fine", so the post does not emit."""
        self.cr.execute("DELETE FROM ir_module_module WHERE name = 'stock_analytic'")
        self.scrap({str(self.account): 100})

        self.jump()

        self.assertEqual(self.notes(), {})

    def test_column_missing_backs_up_nothing(self):
        """Installed but the -u that adds the column never ran: nobody looked, nothing emitted."""
        self.cr.execute("ALTER TABLE stock_scrap DROP COLUMN analytic_distribution")

        self.jump()

        self.assertEqual(self.notes(), {})

    def test_nothing_on_an_upgrade_to_19(self):
        """The pass to 19 keeps stock.scrap: there is nothing to back up."""
        self.write_context(from_version="18.0", to_version="19.0")
        self.scrap({str(self.account): 100})

        pre_odoo.migrate(self.cr, "18.0.1.0.0")

        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (pre_odoo.BACKUP_TABLE,))
        self.assertIsNone(self.cr.fetchone())

    def test_running_twice_leaves_the_same_rows(self):
        """The pre-odoo and the -u can be repeated on the same database; nothing grows or drifts."""
        self.scrap({str(self.account): 100})

        self.jump()
        first = self.notes()
        self.jump()

        self.assertEqual(self.notes(), first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
