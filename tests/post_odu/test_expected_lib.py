#!/usr/bin/env python3
"""Arnés de expected_lib: la parte del carril declarativo que se puede probar
sin Odoo y sin base.

`parse_expected_value` clasifica lo que el dev declaró mirando SOLO la forma
del valor —el tipo real del campo lo cruza el runner, que sí tiene Odoo—, así
que sus ramas se testean acá, en Python puro. Lo que necesita un `env` (que un
ref() resuelva, que un id crudo FAILee, los tipos que quedan fuera del carril)
se prueba sobre una base viva; esto cubre la mitad barata, que es la que se
rompe cuando alguien toca la librería.

Correlo a mano, que este repo no tiene runner de tests:

    python3 tests/post_odu/test_expected_lib.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import expected_lib as X  # noqa: E402


class TestRef(unittest.TestCase):
    def test_exige_modulo_punto_nombre(self):
        with self.assertRaises(ValueError):
            X.ref("sin_modulo")

    def test_identidad_por_xmlid(self):
        self.assertEqual(X.ref("base.main_company"), X.ref("base.main_company"))
        self.assertNotEqual(X.ref("base.main_company"), X.ref("base.user_root"))
        # entra en un set: el runner compara conjuntos de vínculos
        self.assertEqual(len({X.ref("base.main_company"), X.ref("base.main_company")}), 1)

    def test_no_es_igual_a_su_xmlid_pelado(self):
        # un string no es un ref: si lo fuera, un typo pasaría por vínculo
        self.assertNotEqual(X.ref("base.main_company"), "base.main_company")

    def test_company_ref_arma_la_convencion_del_chart_template(self):
        r = X.company_ref(3, "l10n_ar.tax_group_iva")
        self.assertEqual(r.xmlid, "l10n_ar.3_tax_group_iva")
        self.assertEqual(r.company_id, 3)
        self.assertIsInstance(r, X.Ref)  # el runner lo resuelve igual que un ref()


class TestParseExpectedValue(unittest.TestCase):
    """Las ramas de parse_expected_value, una por una."""

    def parse(self, want):
        return X.parse_expected_value(want, "mod/tests/expected_190.py", "mod.rec", "campo")

    def test_ref_suelto_es_un_vinculo(self):
        self.assertEqual(self.parse(X.ref("base.main_company")),
                         ("refs", [X.ref("base.main_company")]))

    def test_company_ref_suelto_es_un_vinculo(self):
        kind, refs = self.parse(X.company_ref(1, "l10n_ar.tax_group_iva"))
        self.assertEqual(kind, "refs")
        self.assertEqual([r.xmlid for r in refs], ["l10n_ar.1_tax_group_iva"])

    def test_lista_de_refs_es_un_x2m(self):
        kind, refs = self.parse([X.ref("base.main_company"), X.ref("base.user_root")])
        self.assertEqual(kind, "refs")
        self.assertEqual([r.xmlid for r in refs],
                         ["base.main_company", "base.user_root"])

    def test_tupla_y_set_de_refs_tambien(self):
        for envoltorio in (tuple, set, frozenset):
            kind, refs = self.parse(envoltorio([X.ref("base.main_company")]))
            self.assertEqual(kind, "refs")
            self.assertEqual([r.xmlid for r in refs], ["base.main_company"])

    def test_vacio_sale_como_escalar(self):
        # qué significa vacío depende del campo, y eso lo sabe el runner
        self.assertEqual(self.parse(None), ("scalar", None))
        self.assertEqual(self.parse([]), ("scalar", []))
        self.assertEqual(self.parse(False), ("scalar", False))

    def test_escalares(self):
        for valor in ("posted", 0, 42, True, 3.5):
            self.assertEqual(self.parse(valor), ("scalar", valor))

    def test_ids_crudos_no_se_deciden_aca(self):
        # sin el campo a la vista un int puede ser un entero esperado legítimo;
        # el FAIL de un id crudo en un relacional lo levanta el runner
        self.assertEqual(self.parse(7), ("scalar", 7))
        self.assertEqual(self.parse([7, 9]), ("scalar", [7, 9]))

    def test_mezclar_refs_con_valores_sueltos_es_error_declarado(self):
        with self.assertRaises(ValueError) as ctx:
            self.parse([X.ref("base.main_company"), 7])
        self.assertIn("mezcla ref()", str(ctx.exception))

    def test_refs_repetidos_son_error_declarado(self):
        with self.assertRaises(ValueError) as ctx:
            self.parse([X.ref("base.main_company"), X.ref("base.main_company")])
        self.assertIn("repite", str(ctx.exception))

    def test_el_mensaje_de_error_ubica_el_caso(self):
        # el dev tiene que poder ir al archivo sin adivinar cuál de N registros
        with self.assertRaises(ValueError) as ctx:
            self.parse([X.ref("base.main_company"), 7])
        for pista in ("expected_190.py", "mod.rec", "campo"):
            self.assertIn(pista, str(ctx.exception))


class TestParseSpec(unittest.TestCase):
    def test_spec_tiene_que_ser_dict(self):
        with self.assertRaises(ValueError):
            X.parse_spec(["campo", "valor"], "k", "mod.rec")

    def test_before_after_se_rechaza_explicito(self):
        # aceptarlo en silencio dejaría un dict que parece contrato sin serlo
        for legacy in ({"before": {}}, {"after": {}}, {"before": {}, "campo": 1}):
            with self.assertRaises(ValueError) as ctx:
                X.parse_spec(legacy, "k", "mod.rec")
            self.assertIn("before/after", str(ctx.exception))

    def test_spec_normal_pasa_tal_cual(self):
        spec = {"campo": 1, "otro": X.ref("base.main_company")}
        self.assertIs(X.parse_spec(spec, "k", "mod.rec"), spec)


class TestSplitField(unittest.TestCase):
    def test_sin_idioma_es_el_campo_tal_cual(self):
        self.assertEqual(X.split_field("name", "k", "mod.rec"), ("name", None))

    def test_con_idioma(self):
        self.assertEqual(X.split_field("name@es_AR", "k", "mod.rec"), ("name", "es_AR"))

    def test_un_idioma_con_arroba_queda_entero(self):
        # sr@latin es un código de idioma de Odoo: se corta solo en la primera @
        self.assertEqual(X.split_field("name@sr@latin", "k", "mod.rec"), ("name", "sr@latin"))

    def test_campo_o_idioma_vacio_es_error_declarado(self):
        for mal in ("@es_AR", "name@"):
            with self.assertRaises(ValueError) as ctx:
                X.split_field(mal, "k", "mod.rec")
            self.assertIn("campo@idioma", str(ctx.exception))


class TestNamespace(unittest.TestCase):
    def test_el_namespace_del_expected_expone_solo_los_dos_helpers(self):
        # un expected_*.py se evalúa con este namespace: si entra algo más,
        # entra código que nadie revisó en un archivo que parece declarativo
        self.assertEqual(sorted(X.NAMESPACE), ["company_ref", "ref"])

    def test_el_namespace_evalua_un_expected_declarativo(self):
        declarado = eval(  # noqa: S307 - es exactamente lo que hace el runner
            "{'company_ids': [ref('base.main_company')], 'state': 'posted'}",
            {"__builtins__": {}}, dict(X.NAMESPACE))
        self.assertEqual(X.parse_expected_value(
            declarado["company_ids"], "k", "mod.rec", "company_ids"),
            ("refs", [X.ref("base.main_company")]))


class TestVersion(unittest.TestCase):
    """El check corre solo los expected del salto que se está probando."""

    def test_version_tag_de_la_serie(self):
        self.assertEqual(X.version_tag("19.0"), "190")
        self.assertEqual(X.version_tag("20.0"), "200")
        self.assertEqual(X.version_tag("saas~18.4"), "184")

    def test_expected_version_del_nombre(self):
        self.assertEqual(X.expected_version("expected_190.py"), "190")
        self.assertEqual(X.expected_version("expected_200.py"), "200")
        for sin_version in ("expected_foo.py", "expected_.py", "expected_190_bis.py",
                            "expected_19.py", "expected_1900.py"):
            self.assertIsNone(X.expected_version(sin_version))

    def test_split_reparte_por_salto(self):
        files = [
            ("stock", "expected_190.py", "p1"),
            ("stock", "expected_200.py", "p2"),
            ("base", "expected_foo.py", "p3"),
        ]
        current, others, unnamed = X.split_by_version(files, "200")
        self.assertEqual(current, [files[1]])
        self.assertEqual(others, [files[0]])
        self.assertEqual(unnamed, [files[2]])

    def test_missing_jump(self):
        own, other = [("stock", "expected_200.py", "p1")], [("stock", "expected_190.py", "p2")]
        self.assertIsNone(X.missing_jump(own, other))
        self.assertEqual(X.missing_jump([], other), "notice")
        self.assertEqual(X.missing_jump([], []), "fail")


class _Repo(unittest.TestCase):
    """Una carpeta modules/ armada en un tmp para cada test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def put(self, rel, content=""):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path


EXPECTED_OK = "EXPECTED = {'res.partner': {ref('base.main_partner'): {'name': 'X'}}}\n"


class TestLoadDeclaration(_Repo):
    def load(self, content):
        return X.load_declaration(self.put("m/tests/expected_200.py", content))

    def test_expected_solo(self):
        decl = self.load(EXPECTED_OK)
        self.assertTrue(decl.expected)
        self.assertIsNone(decl.no_check)
        self.assertFalse(decl.whole_no_check)

    def test_no_check_de_todo_el_archivo(self):
        decl = self.load("NO_CHECK = 'el cambio es de vistas'\n")
        self.assertIsNone(decl.expected)
        self.assertTrue(decl.whole_no_check)

    def test_sin_expected_ni_no_check_es_error(self):
        with self.assertRaises(ValueError):
            self.load("OTRA = 1\n")

    def test_no_check_sin_motivo_es_error(self):
        for mal in ("''", "'   '", "None or 3", "{'s.py': ''}", "{}"):
            with self.assertRaises(ValueError):
                self.load("NO_CHECK = %s\n" % mal)

    def test_no_check_de_archivo_con_expected_es_error(self):
        # dice que no verifica nada y verifica algo: uno de los dos miente
        with self.assertRaises(ValueError):
            self.load(EXPECTED_OK + "NO_CHECK = 'motivo'\n")

    def test_scripts_sin_expected_es_error(self):
        with self.assertRaises(ValueError):
            self.load("SCRIPTS = ['a.py']\nNO_CHECK = {'b.py': 'motivo'}\n")

    def test_script_en_scripts_y_en_no_check_es_error(self):
        with self.assertRaises(ValueError):
            self.load(EXPECTED_OK + "SCRIPTS = ['a.py']\nNO_CHECK = {'a.py': 'motivo'}\n")

    def test_scripts_repetidos_es_error(self):
        with self.assertRaises(ValueError):
            self.load(EXPECTED_OK + "SCRIPTS = ['a.py', 'a.py']\n")


class TestMissingChecks(_Repo):
    """Desde el salto a 20 todo script de modules/ lleva su check (ADR 0037)."""

    def test_folder_tag(self):
        self.assertEqual(X.folder_tag("20.0.1.0.0"), "200")
        self.assertEqual(X.folder_tag("19.0.0.0"), "190")
        self.assertEqual(X.folder_tag("15.0.0.0.0"), "150")
        for no_es in ("0.0.0", "tests", "20.0", "20.1.0.0"):
            self.assertIsNone(X.folder_tag(no_es))

    def test_carpeta_del_salto_sin_expected(self):
        self.put("m/20.0.1.0.0/post-migrate.py")
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("modules/m/20.0.1.0.0/", problems[0])

    def test_carpeta_cubierta_por_expected_o_no_check(self):
        self.put("m/20.0.1.0.0/post-migrate.py")
        self.put("m/tests/expected_200.py", EXPECTED_OK)
        self.put("n/20.0.1.0.0/post-migrate.py")
        self.put("n/tests/expected_200.py", "NO_CHECK = 'solo vistas'\n")
        self.assertEqual(X.missing_checks(self.root, "200"), [])

    def test_carpeta_de_otro_salto_no_cuenta(self):
        self.put("m/19.0.0.0/post-migrate.py")
        self.assertEqual(X.missing_checks(self.root, "200"), [])

    def test_expected_con_solo_no_check_de_scripts_no_cubre_la_carpeta(self):
        self.put("base/20.0.1.0.0/post-migrate.py")
        self.put("base/0.0.0/end-010-a.py")
        self.put("base/tests/expected_200.py", "NO_CHECK = {'end-010-a.py': 'motivo'}\n")
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("20.0.1.0.0", problems[0])

    def test_always_script_por_script(self):
        self.put("base/0.0.0/end-010-a.py")
        self.put("base/0.0.0/end-020-b.py")
        self.put("base/0.0.0/notes.html")
        self.put("base/tests/expected_200.py", EXPECTED_OK + "SCRIPTS = ['end-010-a.py']\n")
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("end-020-b.py", problems[0])

    def test_always_cubierto(self):
        self.put("base/0.0.0/end-010-a.py")
        self.put("base/0.0.0/end-020-b.py")
        self.put("base/tests/expected_200.py",
                 EXPECTED_OK + "SCRIPTS = ['end-010-a.py']\nNO_CHECK = {'end-020-b.py': 'motivo'}\n")
        self.assertEqual(X.missing_checks(self.root, "200"), [])

    def test_always_sin_expected_del_salto(self):
        self.put("base/0.0.0/end-010-a.py")
        self.put("base/tests/expected_190.py", EXPECTED_OK)
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("expected_200.py", problems[0])

    def test_un_script_nombrado_que_no_existe(self):
        # un renombre deja el check apuntando a nada: se avisa
        self.put("base/0.0.0/end-010-a.py")
        self.put("base/tests/expected_200.py",
                 EXPECTED_OK + "SCRIPTS = ['end-010-a.py']\nNO_CHECK = {'end-099-viejo.py': 'motivo'}\n")
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("end-099-viejo.py", problems[0])

    def test_expected_ilegible(self):
        self.put("m/20.0.1.0.0/post-migrate.py")
        self.put("m/tests/expected_200.py", "EXPECTED = {\n")
        problems = X.missing_checks(self.root, "200")
        self.assertEqual(len(problems), 1)
        self.assertIn("ilegible", problems[0])

    def test_enforced_tags(self):
        self.put("m/19.0.0.0/post-migrate.py")
        self.assertEqual(X.enforced_tags(self.root), ["200"])
        self.put("m/21.0.1.0.0/post-migrate.py")
        self.put("n/tests/expected_220.py", EXPECTED_OK)
        self.assertEqual(X.enforced_tags(self.root), ["200", "210", "220"])
        self.assertFalse(X.enforced("190"))
        self.assertTrue(X.enforced("200"))

    def test_el_repo_no_tiene_scripts_sin_check(self):
        # el mismo control del job missing-checks, sobre este repo
        root = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))), "modules")
        self.assertEqual(
            [p for tag in X.enforced_tags(root) for p in X.missing_checks(root, tag)], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
