"""Los scripts de `pre_upgrade_scripts` corridos dos veces sobre la misma base.

Un `-u` que falla se retoma sobre la base que quedó, así que estos scripts —que no van
atados a la versión de ningún módulo— vuelven a correr enteros sobre datos que la corrida
anterior ya migró. Acá se prueba la segunda vuelta de los tres que tocan datos que no se
pueden rehacer.

Crean y borran su propia base de Postgres. Odoo no tiene que estar corriendo, solo
importable.

    /home/odoo/venv/bin/python pre_upgrade_scripts/tests/test_resumed_run.py

`ODOO_PATH` y `UPGRADE_TEST_DB` los apuntan a otro checkout o a otra base.
"""

import importlib.util
import os
import subprocess
import sys
import unittest

ODOO_PATH = os.environ.get("ODOO_PATH", "/home/odoo/src/odoo")
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_resumed_run_test")
ALWAYS = os.path.join(REPO, "pre_upgrade_scripts", "always")
SCRIPTS_180_190 = os.path.join(REPO, "pre_upgrade_scripts", "180_190")

try:
    # El venv trae `odoo` como namespace, con el `util` de `odoo.upgrade` adentro. Poner el
    # checkout en el path primero lo convierte en paquete regular y ese `util` desaparece,
    # así que solo se agrega cuando `odoo` no se importa de otro lado.
    import odoo.upgrade  # noqa: E402
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: E402

if REPO not in odoo.upgrade.__path__:
    odoo.upgrade.__path__.append(REPO)

import odoo.sql_db  # noqa: E402

from odoo.release import major_version  # noqa: E402

MAJOR = major_version.split(".")[0]
PREVIOUS_MAJOR = str(int(MAJOR) - 1)


def _load(folder, name):
    """Cargar un script por path: las carpetas de `pre_upgrade_scripts` no son paquetes."""
    spec = importlib.util.spec_from_file_location("script_under_test_%s" % name, os.path.join(folder, name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResumedRunCase(unittest.TestCase):
    """Base con la conexión a una base vacía, donde cada test arma las tablas que toca."""

    @classmethod
    def setUpClass(cls):
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)
        subprocess.run(["createdb", TEST_DB], check=True)
        # El cursor de Odoo y no uno de psycopg2: los scripts arman sus consultas con
        # `odoo.tools.SQL`, que solo este sabe ejecutar.
        cls.cr = odoo.sql_db.db_connect(TEST_DB).cursor()

    @classmethod
    def tearDownClass(cls):
        cls.cr.close()
        odoo.sql_db.close_db(TEST_DB)
        subprocess.run(["dropdb", "--if-exists", TEST_DB], check=True)

    def setUp(self):
        self.cr = type(self).cr

    def _drop(self, *tables):
        for table in tables:
            self.cr.execute("DROP TABLE IF EXISTS %s" % table)


class TestReactivateViews(ResumedRunCase):
    def setUp(self):
        super().setUp()
        self.script = _load(ALWAYS, "reactivate_views.py")
        self._drop("ir_ui_view", self.script.BACKUP_TABLE)
        self.cr.execute("CREATE TABLE ir_ui_view (id serial PRIMARY KEY, active boolean)")
        self.cr.execute("INSERT INTO ir_ui_view (id, active) VALUES (1, false), (2, false)")
        self.cr.execute("CREATE TABLE %s (id integer)" % self.script.BACKUP_TABLE)
        self.cr.execute("INSERT INTO %s (id) VALUES (1), (2)" % self.script.BACKUP_TABLE)

    def _active(self):
        self.cr.execute("SELECT id FROM ir_ui_view WHERE active ORDER BY id")
        return [row[0] for row in self.cr.fetchall()]

    def test_reactivates_the_views_the_upgrade_disabled(self):
        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._active(), [1, 2])

    def test_the_resumed_run_does_not_bring_back_views_disabled_on_purpose(self):
        """Cada vista se re-activa una vez, la que desactivó el upgrade de Odoo. Las que
        apaga nuestro `-u` —algunas por data, como `stock_ux`— tienen que quedarse apagadas,
        y en la corrida retomada su módulo ya no vuelve a correr para apagarlas de nuevo."""
        self.script.migrate(self.cr, "18.0.1.3")
        self.cr.execute("UPDATE ir_ui_view SET active = false WHERE id = 2")

        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._active(), [1])

    def test_the_backup_is_consumed(self):
        """Se usa una vez y se va: lo que el `-u` apague después no es asunto suyo."""
        self.script.migrate(self.cr, "18.0.1.3")

        self.cr.execute("SELECT to_regclass('%s')" % self.script.BACKUP_TABLE)
        self.assertIsNone(self.cr.fetchall()[0][0])


class TestClearPreviousCustomerNotes(ResumedRunCase):
    def setUp(self):
        super().setUp()
        self.script = _load(ALWAYS, "clear_previous_customer_notes.py")
        self._drop(self.script.TABLE)
        self.cr.execute(
            """
            CREATE TABLE %s (
                slug varchar PRIMARY KEY,
                module varchar NOT NULL,
                script varchar NOT NULL,
                vals jsonb NOT NULL,
                created_at timestamp NOT NULL
            )
            """
            % self.script.TABLE
        )
        self.cr.execute(
            "INSERT INTO %s (slug, module, script, vals, created_at) VALUES"
            " ('vieja', 'sale', 'sale/%s.0.1.0/post-migration.py', '{}'::jsonb, now()),"
            " ('nueva', 'sale', 'sale/%s.0.1.0/post-migration.py', '{}'::jsonb, now())"
            % (self.script.TABLE, PREVIOUS_MAJOR, MAJOR)
        )

    def _slugs(self):
        self.cr.execute("SELECT slug FROM %s ORDER BY slug" % self.script.TABLE)
        return [row[0] for row in self.cr.fetchall()]

    def test_clears_what_the_previous_upgrade_left(self):
        """El guard del helper aborta el upgrade si el slug quedó tomado por otro script."""
        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._slugs(), ["nueva"])

    def test_the_resumed_run_keeps_the_notes_of_the_modules_already_upgraded(self):
        """Esos módulos no vuelven a correr, así que nadie reescribe sus valores."""
        self.script.migrate(self.cr, "18.0.1.3")
        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._slugs(), ["nueva"])

    def test_a_version_folder_that_says_no_major_keeps_its_note(self):
        """El `VERSION_RE` del helper acepta carpetas sin major: perder esa nota en silencio
        es la misma clase de bug que este script viene a evitar."""
        self.cr.execute(
            "INSERT INTO %s (slug, module, script, vals, created_at) VALUES"
            " ('rara', 'sale', 'sale/1.0/post-migration.py', '{}'::jsonb, now())" % self.script.TABLE
        )

        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._slugs(), ["nueva", "rara"])

    def test_does_nothing_without_the_table(self):
        self._drop(self.script.TABLE)

        self.script.migrate(self.cr, "18.0.1.3")


class TestHrContractOrphanGroup(ResumedRunCase):
    def setUp(self):
        super().setUp()
        self.script = _load(SCRIPTS_180_190, "hr_contract_orphan_group.py")
        self._drop("res_groups", "ir_model_data", self.script.BACKUP_TABLE)
        self.cr.execute("CREATE TABLE res_groups (id serial PRIMARY KEY, create_date timestamp)")
        self.cr.execute("INSERT INTO res_groups (id, create_date) VALUES (1, '2020-01-01')")
        self.cr.execute(
            """
            CREATE TABLE ir_model_data (
                id serial PRIMARY KEY, module varchar, name varchar, model varchar, res_id integer,
                noupdate boolean, create_date timestamp, write_date timestamp,
                create_uid integer, write_uid integer
            )
            """
        )
        self.cr.execute(
            "CREATE TABLE %s (group_id integer PRIMARY KEY, module varchar, name varchar, create_date timestamp)"
            % self.script.BACKUP_TABLE
        )
        self.cr.execute(
            "INSERT INTO %s (group_id, module, name, create_date) VALUES (1, %%s, %%s, '2020-01-01')"
            % self.script.BACKUP_TABLE,
            (self.script.GHOST_MODULE, self.script.GHOST_NAME),
        )

    def _xmlids(self):
        self.cr.execute("SELECT module, name FROM ir_model_data WHERE model = 'res.groups' ORDER BY id")
        return self.cr.fetchall()

    def test_restores_the_xmlid_the_upgrade_dropped(self):
        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._xmlids(), [(self.script.TARGET_MODULE, self.script.GHOST_NAME)])

    def test_the_resumed_run_leaves_the_repair_of_the_previous_one_as_is(self):
        """Reparado en el intento anterior y ya commiteado: la corrida retomada no encuentra
        el respaldo, lo dice en el log y no toca nada."""
        self.script.migrate(self.cr, "18.0.1.3")

        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._xmlids(), [(self.script.TARGET_MODULE, self.script.GHOST_NAME)])


class TestRemitoDigitalBackup(ResumedRunCase):
    def setUp(self):
        super().setUp()
        self.script = _load(SCRIPTS_180_190, "l10n_ar_stock_remito_digital_backup.py")
        self._drop(
            "stock_book",
            "stock_picking",
            "stock_picking_voucher",
            "_upgrade_stock_book",
            "_upgrade_stock_picking_voucher",
        )
        self.cr.execute("CREATE TABLE stock_book (id serial PRIMARY KEY, name varchar)")
        self.cr.execute("INSERT INTO stock_book (id, name) VALUES (1, 'A0001')")
        self.cr.execute("CREATE TABLE stock_picking (id serial PRIMARY KEY, book_id integer)")
        self.cr.execute("INSERT INTO stock_picking (id, book_id) VALUES (1, 1)")

    def _backup_names(self):
        self.cr.execute("SELECT name FROM _upgrade_stock_book ORDER BY id")
        return [row[0] for row in self.cr.fetchall()]

    def _backup_book_ids(self):
        self.cr.execute("SELECT _upgrade_book_id FROM stock_picking ORDER BY id")
        return [row[0] for row in self.cr.fetchall()]

    def test_backs_up_what_the_upgrade_is_about_to_drop(self):
        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._backup_names(), ["A0001"])
        self.assertEqual(self._backup_book_ids(), [1])

    def test_the_resumed_run_does_not_overwrite_the_backup_with_migrated_data(self):
        """En la corrida retomada los datos vigentes ya pueden ser los que migró el intento
        anterior: rehacer la copia desde ahí deja al post sin el original."""
        self.script.migrate(self.cr, "18.0.1.3")
        self.cr.execute("UPDATE stock_book SET name = 'ya migrado'")
        self.cr.execute("UPDATE stock_picking SET book_id = NULL")

        self.script.migrate(self.cr, "18.0.1.3")

        self.assertEqual(self._backup_names(), ["A0001"])
        self.assertEqual(self._backup_book_ids(), [1])

    def test_does_nothing_without_the_tables(self):
        self._drop("stock_book", "stock_picking", "_upgrade_stock_book")

        self.script.migrate(self.cr, "18.0.1.3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
