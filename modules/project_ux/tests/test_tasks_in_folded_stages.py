"""What the project_ux post-migration tells the customer, case by case.

The test creates and drops its own Postgres database with the tables the script reads, so
it needs no Odoo running and no network, only an importable ``odoo.upgrade``.

    /home/odoo/venv/bin/python modules/project_ux/tests/test_tasks_in_folded_stages.py

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
TEST_DB = os.environ.get("UPGRADE_TEST_DB", "upgrade_project_ux_folded_stages_test")
SCRIPT = os.path.join(REPO, "modules", "project_ux", "20.0.1.0.0", "post-migration.py")

try:
    import odoo.upgrade  # noqa: F401
except ImportError:
    sys.path.insert(0, ODOO_PATH)

    import odoo.upgrade  # noqa: F401

sys.path.insert(0, os.path.join(REPO, "lib"))

import psycopg2  # noqa: E402

from odoo.tools import SQL  # noqa: E402

from oba.customer_note import TABLE as NOTES  # noqa: E402


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


def _load_script():
    """Load the script by path: a version folder is not a package and the name has a dash."""
    spec = importlib.util.spec_from_file_location("project_ux_post_migration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _load_script()

SCHEMA = """
    CREATE TABLE ir_module_module (id serial PRIMARY KEY, name varchar UNIQUE NOT NULL, state varchar NOT NULL);
    CREATE TABLE project_project (id serial PRIMARY KEY, name jsonb);
    CREATE TABLE project_task_type (
        id serial PRIMARY KEY,
        name jsonb,
        fold boolean,
        state_change boolean,
        task_state varchar
    );
    CREATE TABLE project_task (
        id serial PRIMARY KEY,
        name varchar,
        state varchar,
        stage_id integer REFERENCES project_task_type (id),
        project_id integer REFERENCES project_project (id),
        active boolean
    );
    CREATE TABLE ir_filters (
        id serial PRIMARY KEY,
        name varchar,
        model_id varchar,
        domain text,
        active boolean
    );
"""


class FoldedStagesCase(unittest.TestCase):
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
        self.cr.execute(
            "DROP TABLE IF EXISTS project_task, project_task_type, project_project, "
            "ir_filters, ir_module_module, %s" % NOTES
        )
        self.cr.execute(SCHEMA)
        self.installed("project_ux")
        self.project = self.project_("Proyecto")

    def installed(self, module, state="installed"):
        self.cr.execute("INSERT INTO ir_module_module (name, state) VALUES (%s, %s)", (module, state))

    def project_(self, name):
        self.cr.execute("INSERT INTO project_project (name) VALUES (%s) RETURNING id", (json.dumps({"en_US": name}),))
        return self.cr.fetchone()[0]

    def stage(self, name, fold=True, task_state=None, lang="en_US"):
        self.cr.execute(
            "INSERT INTO project_task_type (name, fold, task_state) VALUES (%s, %s, %s) RETURNING id",
            (json.dumps({lang: name}), fold, task_state),
        )
        return self.cr.fetchone()[0]

    def task(self, name, stage_id, state="01_in_progress", active=True):
        self.cr.execute(
            "INSERT INTO project_task (name, stage_id, project_id, state, active) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (name, stage_id, self.project, state, active),
        )
        return self.cr.fetchone()[0]

    def filter_(self, name, model_id="project.task", domain="[('is_closed', '=', False)]", active=True):
        self.cr.execute(
            "INSERT INTO ir_filters (name, model_id, domain, active) VALUES (%s, %s, %s, %s)",
            (name, model_id, domain, active),
        )

    def run_script(self):
        script.migrate(self.cr, "19.0.1.0.0")

    def notes(self):
        self.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (NOTES,))
        if not self.cr.fetchone():
            return {}
        self.cr.execute("SELECT key, value FROM %s" % NOTES)
        return dict(self.cr.fetchall())


class TestWhatIsReported(FoldedStagesCase):
    def test_task_in_a_closing_folded_stage_is_listed_to_be_closed(self):
        """The stage already says Done closes it, so the task is finished and only its
        state stayed open. After the jump it reads as open: somebody has to close it.
        """
        stage = self.stage("Realizado", task_state="1_done")
        task_id = self.task("Terminada", stage)

        self.run_script()

        notes = self.notes()
        self.assertEqual(notes["project_ux_tareas_a_cerrar_total"], 1)
        self.assertEqual(
            notes["project_ux_tareas_a_cerrar"],
            [{"id": task_id, "tarea": "Terminada", "etapa": "Realizado", "proyecto": "Proyecto"}],
        )
        self.assertEqual(notes["project_ux_tareas_que_pasan_a_abiertas_total"], 0)

    def test_task_in_a_folded_stage_without_closing_state_is_only_counted(self):
        """This is the group the change corrects: parked in Stand by and still pending, so
        it has to read as open. It is counted, not listed to be closed.
        """
        self.task("Parada", self.stage("Stand by"))

        self.run_script()

        notes = self.notes()
        self.assertEqual(notes["project_ux_tareas_que_pasan_a_abiertas_total"], 1)
        self.assertEqual(notes["project_ux_tareas_a_cerrar_total"], 0)
        self.assertEqual(notes["project_ux_tareas_a_cerrar"], [])

    def test_already_closed_task_is_not_reported(self):
        """Its state is Done, so it counted as closed before and still does: nothing
        changes for it, and reporting it would inflate the note with noise.
        """
        self.task("Hecha", self.stage("Stand by"), state="1_done")
        self.task("Cancelada", self.stage("Cancelada", task_state="1_canceled"), state="1_canceled")

        self.run_script()

        notes = self.notes()
        self.assertEqual(notes["project_ux_tareas_a_cerrar_total"], 0)
        self.assertEqual(notes["project_ux_tareas_que_pasan_a_abiertas_total"], 0)

    def test_task_in_an_unfolded_stage_is_not_reported(self):
        """is_closed only ever meant "folded stage", so an open task in an open column was
        open before and after. If this one appears, the script lost the fold filter.
        """
        self.task("En curso", self.stage("En progreso", fold=False))

        self.run_script()

        self.assertEqual(self.notes()["project_ux_tareas_que_pasan_a_abiertas_total"], 0)

    def test_archived_task_is_not_reported(self):
        """Nobody is going to review an archived task, and the Open/Closed filters do not
        show it either.
        """
        self.task("Archivada", self.stage("Realizado", task_state="1_done"), active=False)

        self.run_script()

        self.assertEqual(self.notes()["project_ux_tareas_a_cerrar_total"], 0)

    def test_stage_name_without_en_us_still_reads(self):
        """Translated names are jsonb. A record that only ever had another language has no
        en_US key, and without the fallback the note would show a null stage.
        """
        self.task("Parada", self.stage("En espera", lang="es_AR"))

        self.run_script()

        self.assertEqual(
            self.notes()["project_ux_etapas_plegadas_sin_cierre"], [{"etapa": "En espera", "columnas": 1}]
        )


class TestStagesAndFilters(FoldedStagesCase):
    def test_folded_stage_without_closing_state_is_listed(self):
        """These are the columns that stop closing a task. The one that declares a closing
        state keeps closing it, so it is not something to review.
        """
        self.stage("Stand by")
        # The same stage name in two projects: one entry, two columns.
        self.stage("Stand by")
        self.stage("Próximas Versiones", task_state="01_in_progress")
        self.stage("Realizado", task_state="1_done")
        self.stage("En progreso", fold=False)

        self.run_script()

        self.assertEqual(
            self.notes()["project_ux_etapas_plegadas_sin_cierre"],
            [{"etapa": "Próximas Versiones", "columnas": 1}, {"etapa": "Stand by", "columnas": 2}],
        )

    def test_saved_filter_searching_is_closed_is_listed(self):
        """It keeps working and starts answering a different question. A filter on another
        model, or archived, is not the customer's problem.
        """
        self.filter_("Pendientes")
        self.filter_("Sin is_closed", domain="[('state', '=', '01_in_progress')]")
        self.filter_("Otro modelo", model_id="project.project")
        self.filter_("Archivado", active=False)

        self.run_script()

        self.assertEqual(self.notes()["project_ux_filtros_guardados_con_is_closed"], ["Pendientes"])


class TestWhenToEmit(FoldedStagesCase):
    def test_nothing_to_report_still_emits(self):
        """"Nothing was left pending" is a result, and the row is what lets the message say
        it. Without emitting there is no row and the note is archived.
        """
        self.run_script()

        notes = self.notes()
        self.assertEqual(notes["project_ux_tareas_a_cerrar_total"], 0)
        self.assertEqual(notes["project_ux_tareas_a_cerrar"], [])
        self.assertEqual(notes["project_ux_etapas_plegadas_sin_cierre"], [])
        self.assertEqual(notes["project_ux_filtros_guardados_con_is_closed"], [])

    def test_module_not_installed_emits_nothing(self):
        """Without the module is_closed never changed meaning, so there is nothing to tell
        and a zero would read as "we checked and you are fine".
        """
        self.cr.execute("DELETE FROM ir_module_module WHERE name = 'project_ux'")
        self.task("Parada", self.stage("Stand by"))

        self.run_script()

        self.assertEqual(self.notes(), {})

    def test_running_twice_leaves_the_same_rows(self):
        """A -u can be repeated on the same database; the note must not grow or drift."""
        self.task("Terminada", self.stage("Realizado", task_state="1_done"))

        self.run_script()
        first = self.notes()
        self.run_script()

        self.assertEqual(self.notes(), first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
