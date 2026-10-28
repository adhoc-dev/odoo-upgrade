#!/usr/bin/env python3
"""Static checks on modules/base/19.0.0.0/end-migration.py that need no Odoo.

A helper defined twice at module level is silently shadowed by the last
definition. `table_exists` was defined twice and the permissive copy won, so the
FK remap tried to UPDATE SQL views such as hr_employee_public.

Run by hand, this repo has no test runner:

    python3 tests/base/test_end_migration_helpers.py
"""

import ast
import collections
import contextlib
import json
import logging
import os
import unittest

PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "modules",
    "base",
    "19.0.0.0",
    "end-migration.py",
)


class FakeCursor:
    def __init__(self):
        self.query = None

    def execute(self, query, params=None):
        self.query = query

    def fetchone(self):
        return (True,)


class FakeParams:
    """ir.config_parameter over a database that only keeps what was committed."""

    def __init__(self, db):
        self.db = db

    def sudo(self):
        return self

    def get_param(self, key, default=False):
        return self.db.pending.get(key, default)

    def set_param(self, key, value):
        # Odoo borra el parámetro cuando el valor es False
        if value is False:
            self.db.pending.pop(key, None)
        else:
            self.db.pending[key] = value


class FakeCr:
    def __init__(self, db):
        self.db = db

    def commit(self):
        self.db.committed = dict(self.db.pending)


class FakeEnv:
    def __init__(self, db):
        self.cr = FakeCr(db)
        self.models = {"ir.config_parameter": FakeParams(db)}

    def __getitem__(self, model):
        return self.models[model]


class FakeRecords:
    """Lo mínimo de un recordset que usa merge_scope: ids, browse y exists.

    ``ids`` es lo que el search trae hoy; ``alive`` es lo que existe en la
    base. Son distintos a propósito: el registro fusionado sigue existiendo,
    archivado y colgando de la matriz, así que el search por la sucursal ya no
    lo trae pero exists() sí. Lo que de verdad desaparece es lo que la fusión
    borra (un account.tax.group sin impuestos).
    """

    def __init__(self, ids, alive=None):
        self.ids = list(ids)
        self.alive = set(ids) if alive is None else set(alive)

    def browse(self, ids):
        return FakeRecords(ids, self.alive)

    def exists(self):
        return FakeRecords([i for i in self.ids if i in self.alive], self.alive)


class FakeDb:
    def __init__(self):
        self.committed = {}
        self.pending = {}

    def env(self):
        """A new run: it only sees what the previous one committed."""
        self.pending = dict(self.committed)
        return FakeEnv(self)


class FakeUserError(Exception):
    pass


class TestEndMigrationHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH) as f:
            cls.tree = ast.parse(f.read())

    def test_no_helper_defined_twice(self):
        names = collections.Counter(
            node.name for node in self.tree.body if isinstance(node, ast.FunctionDef)
        )
        duplicated = sorted(name for name, count in names.items() if count > 1)
        self.assertEqual(duplicated, [])

    def test_table_exists_ignores_views(self):
        # The last definition is the one Python keeps
        node = [
            n
            for n in self.tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "table_exists"
        ][-1]
        namespace = {}
        exec(compile(ast.Module([node], []), PATH, "exec"), namespace)
        cr = FakeCursor()
        namespace["table_exists"](cr, "hr_employee_public")
        self.assertIn("BASE TABLE", cr.query)

    def _helpers(self):
        names = {
            "_done_steps",
            "step_pending",
            "step_done",
            "clear_progress",
            "_merge_state",
            "_save_merge_state",
            "merge_scope",
            "merge_step",
            "load_merged_ids",
            "remember_merged",
        }
        constants = {
            "PROGRESS_PARAM",
            "MERGE_STATE_PARAM",
            "MERGE_STATE_MODELS",
            "MERGE_FROZEN_SCOPE_MODELS",
            "MERGED_IDS",
        }
        nodes = [
            n
            for n in self.tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in names)
            or (
                isinstance(n, ast.Assign)
                and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id in constants
            )
        ]
        namespace = {
            "json": json,
            "_logger": logging.getLogger("test"),
            "contextmanager": contextlib.contextmanager,
        }
        exec(compile(ast.Module(nodes, []), PATH, "exec"), namespace)
        return namespace

    def _run(self, h, db, steps, work, fail_at=None):
        """A loop shaped like the merge one: each step does its work and commits with its mark."""
        env = db.env()
        for key in steps:
            if h["step_pending"](env, key):
                work.append(key)
                if key == fail_at:
                    # The step did its work and died before committing it
                    raise FakeUserError(key)
                h["step_done"](env, key)

    def test_a_failed_run_resumes_at_the_step_that_broke(self):
        h = self._helpers()
        db = FakeDb()
        steps = ["merge:1:2:0-1.2", "merge:1:2:2:account.tax", "merge:1:2:2:account.group", "merge:1:2:2.1-2.2"]
        first = []
        with self.assertRaises(FakeUserError):
            self._run(h, db, steps, first, fail_at=steps[2])
        # The failed step did its work, but it was not committed
        self.assertEqual(first, steps[:3])
        self.assertEqual(json.loads(db.committed[h["PROGRESS_PARAM"]]), steps[:2])

        second = []
        self._run(h, db, steps, second)
        self.assertEqual(second, steps[2:])
        self.assertEqual(json.loads(db.committed[h["PROGRESS_PARAM"]]), steps)

        # A third run finds everything done and touches nothing
        third = []
        self._run(h, db, steps, third)
        self.assertEqual(third, [])

        # And when the migration ends the mark does not stay in the database
        env = db.env()
        h["clear_progress"](env)
        env.cr.commit()
        self.assertNotIn(h["PROGRESS_PARAM"], db.committed)

    def test_every_step_opened_is_marked_done(self):
        # A step_pending without its step_done never commits: the next run would repeat it
        for name in ("migrate", "migrate_store_to_branch"):
            node = [
                n for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name == name
            ][-1]
            keys = collections.defaultdict(collections.Counter)
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in ("step_pending", "step_done")
                ):
                    keys[call.func.id][ast.unparse(call.args[1])] += 1
            self.assertTrue(keys["step_pending"], name)
            self.assertEqual(set(keys["step_pending"]), set(keys["step_done"]), name)

    def _merge_loop(self, h, db, step, in_branch, fail_at=None, alive=None):
        """El loop de handle_merge_or_move, con lo que al resume le importa.

        Espeja el código real: la estructura queda atada por
        test_the_merge_marks_every_record_it_finishes.
        """
        env = db.env()
        processed = []
        if not h["step_pending"](env, step):
            return processed
        # El search solo trae lo que todavía cuelga de la sucursal: lo fusionado
        # ya se movió a la matriz.
        records = h["merge_scope"](
            env, step, FakeRecords(sorted(in_branch), alive=alive)
        )
        for rec_id in records.ids:
            rec_step = "%s:%s" % (step, rec_id)
            if not h["step_pending"](env, rec_step):
                continue
            with h["merge_step"](env, rec_step):
                if rec_id == fail_at:
                    # El impuesto se estaba fusionando cuando murió el pod
                    raise FakeUserError(rec_id)
                h["remember_merged"](env, "account.tax", rec_id, 1000 + rec_id)
                in_branch.discard(rec_id)
                processed.append(rec_id)
        h["step_done"](env, step)
        return processed

    def test_the_merge_resumes_at_the_record_that_broke(self):
        # La fusión de impuestos de una base grande no entra en el tiempo del
        # job. Con la marca por modelo cada reintento volvía a empezar por el
        # primero; con la marca por registro, avanza.
        h = self._helpers()
        db = FakeDb()
        step = "merge:3:4:2:account.tax"
        in_branch = {11, 22, 33, 44}

        alive = set(in_branch)
        first = []
        with self.assertRaises(FakeUserError):
            first = self._merge_loop(
                h, db, step, in_branch, fail_at=33, alive=alive
            )
        self.assertEqual(first, [])  # la excepción se lleva el valor de retorno
        self.assertEqual(
            json.loads(db.committed[h["PROGRESS_PARAM"]]),
            ["%s:%s" % (step, i) for i in (11, 22)],
        )

        second = self._merge_loop(h, db, step, in_branch, alive=alive)
        self.assertEqual(second, [33, 44])  # no repite 11 ni 22

        # Una tercera corrida encuentra el modelo cerrado y no toca nada
        self.assertEqual(
            self._merge_loop(h, db, step, in_branch, alive=alive), []
        )

    def test_the_merged_ids_survive_a_resume(self):
        # account.fiscal.position compara contra impuestos ya fusionados: si la
        # corrida que retoma arranca con MERGED_IDS vacío, los compara contra
        # ids de la sucursal que ya no corresponden.
        h = self._helpers()
        db = FakeDb()
        step = "merge:3:4:2:account.tax"
        in_branch = {11, 22, 33}
        alive = set(in_branch)

        with self.assertRaises(FakeUserError):
            self._merge_loop(h, db, step, in_branch, fail_at=33, alive=alive)

        # Arranca la corrida siguiente: memoria limpia, como un proceso nuevo
        h["MERGED_IDS"].clear()
        env = db.env()
        h["load_merged_ids"](env)
        self.assertEqual(h["MERGED_IDS"]["account.tax"], {11: 1011, 22: 1022})

        self._merge_loop(h, db, step, in_branch, alive=alive)
        h["MERGED_IDS"].clear()
        h["load_merged_ids"](db.env())
        self.assertEqual(
            h["MERGED_IDS"]["account.tax"], {11: 1011, 22: 1022, 33: 1033}
        )

        # Terminada la fusión no queda nada de esto en la base
        env = db.env()
        h["clear_progress"](env)
        env.cr.commit()
        self.assertNotIn(h["MERGE_STATE_PARAM"], db.committed)

    def test_the_branch_records_stay_in_scope_after_a_resume(self):
        # drop_branch_vat_from_products necesita TODOS los impuestos que vinieron
        # de la sucursal, y los ya fusionados no cuelgan más de ella.
        h = self._helpers()
        db = FakeDb()
        step = "merge:3:4:2:account.tax"
        in_branch = {11, 22, 33, 44}
        alive = set(in_branch)

        with self.assertRaises(FakeUserError):
            self._merge_loop(h, db, step, in_branch, fail_at=33, alive=alive)
        self.assertEqual(in_branch, {33, 44})  # 11 y 22 ya se movieron a la matriz

        env = db.env()
        records = h["merge_scope"](
            env, step, FakeRecords(sorted(in_branch), alive=alive)
        )
        self.assertEqual(records.ids, [11, 22, 33, 44])

        # Y lo que la fusión borró de verdad no vuelve como registro fantasma
        alive.discard(22)
        records = h["merge_scope"](
            env, step, FakeRecords(sorted(in_branch), alive=alive)
        )
        self.assertEqual(records.ids, [11, 33, 44])

    def test_the_merge_marks_every_record_it_finishes(self):
        # Ata el espejo de _merge_loop al código real: si la estructura del
        # loop cambia, este test lo dice antes que la migración de un cliente.
        node = [
            n
            for n in self.tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "handle_merge_or_move"
        ][-1]
        calls = collections.Counter()
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                calls[call.func.id] += 1
        # El conjunto se congela, cada registro se marca al terminar y el modelo
        # se cierra al final
        self.assertEqual(calls["merge_scope"], 1)
        self.assertEqual(calls["merge_step"], 1)
        self.assertEqual(calls["step_pending"], 2)  # el del modelo y el del registro
        self.assertEqual(calls["step_done"], 1)  # el del modelo; el registro lo cierra merge_step

        loops = [n for n in ast.walk(node) if isinstance(n, ast.For)]
        rec_loop = [n for n in loops if ast.unparse(n.iter) == "records_b"]
        self.assertEqual(len(rec_loop), 1)
        # Todo el trabajo del registro vive adentro del with: un continue del
        # cuerpo sale por el __exit__ y deja la marca igual
        body = rec_loop[0].body
        self.assertIsInstance(body[-1], ast.With)  # el with cierra el cuerpo
        self.assertEqual(
            [type(n) for n in body[:-1]], [ast.Assign, ast.If]
        )  # rec_step y la guarda, nada de trabajo fuera del with

    def test_migrate_delegates_the_merge_step_to_the_model_handler(self):
        node = [
            n
            for n in self.tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "migrate"
        ][-1]
        calls = [
            c
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id == "handle_merge_or_move"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual([kw.arg for kw in calls[0].keywords], ["step"])


    def test_a_continue_inside_the_step_still_marks_it(self):
        # El cuerpo del loop corta con continue en tres casos (el tax.group que
        # se borra, el impuesto inactivo que se mueve). Salir así tiene que
        # dejar la marca igual, o la corrida siguiente los reprocesa.
        h = self._helpers()
        db = FakeDb()
        env = db.env()
        done = []
        for rec_id in (11, 22):
            with h["merge_step"](env, "merge:3:4:2:account.tax:%s" % rec_id):
                done.append(rec_id)
                if rec_id == 11:
                    continue
        self.assertEqual(done, [11, 22])
        self.assertEqual(
            json.loads(db.committed[h["PROGRESS_PARAM"]]),
            ["merge:3:4:2:account.tax:11", "merge:3:4:2:account.tax:22"],
        )

    def test_only_the_models_someone_reads_back_are_persisted(self):
        # El estado se reescribe entero con cada registro: persistir
        # account.analytic.line, que puede traer cien mil, haría de la fusión un
        # cuadrático. Se guarda lo que _canonical_id consulta después.
        h = self._helpers()
        db = FakeDb()
        env = db.env()
        h["MERGED_IDS"].clear()

        h["remember_merged"](env, "account.analytic.line", 7, 8)
        self.assertEqual(h["MERGED_IDS"]["account.analytic.line"], {7: 8})
        self.assertNotIn(h["MERGE_STATE_PARAM"], db.pending)

        h["remember_merged"](env, "account.tax", 7, 8)
        self.assertIn(h["MERGE_STATE_PARAM"], db.pending)
        self.assertEqual(
            json.loads(db.pending[h["MERGE_STATE_PARAM"]])["merged"],
            {"account.tax": {"7": 8}},
        )


if __name__ == "__main__":
    unittest.main()
