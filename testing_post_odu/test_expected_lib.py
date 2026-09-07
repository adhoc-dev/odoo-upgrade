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

    python3 testing_post_odu/test_expected_lib.py
"""

import os
import sys
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
