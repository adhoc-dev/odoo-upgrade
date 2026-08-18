# Primitivas del formato declarativo de tests de migración.
# Diseño: actua-20-project/decisions/0007-el-check-es-el-unico-carril.md
#
# Un test de migración es un archivo <modulo>/tests/expected_*.py que define
#     EXPECTED = { <modelo>: { ref(...): {<campo>: <valor esperado>} } }
# donde el valor esperado es el que debe quedar DESPUÉS de la migración. No hay
# contraparte "before": nada se verifica sobre la base fuente (ADR 0007).
# Este módulo provee las primitivas con las que se escribe ese dict y el
# descubrimiento/parseo que usa check_expected.py.
#
# Sin dependencias de Odoo: importable desde cualquier runner y desde
# odoo shell por igual.

import os


class Ref:
    """Registro conocido por xmlid. Sale de la data de prueba que traen los
    módulos instalados en la base canónica, o de la inyección de
    upgrade-prepare-demo para los casos que esa data no cubre. El estado de
    partida se da por bueno —la base que recibimos es la base candidata ya
    preparada—; check_expected.py resuelve el xmlid post -u y compara lo
    declarado. Sin prepare, sin gate previo, sin estado runtime."""

    def __init__(self, xmlid):
        if "." not in xmlid:
            raise ValueError("ref() espera 'modulo.nombre', recibió %r" % xmlid)
        self.xmlid = xmlid

    def __hash__(self):
        return hash(("ref", self.xmlid))

    def __eq__(self, other):
        return isinstance(other, Ref) and other.xmlid == self.xmlid

    def __repr__(self):
        return "ref(%r)" % self.xmlid


class CompanyRef(Ref):
    """Xmlid escopeado por compañía, convención de account.chart.template:
    '{modulo}.{company_id}_{nombre}'."""

    def __init__(self, company_id, xmlid):
        module, name = xmlid.split(".", 1)
        super().__init__("%s.%s_%s" % (module, company_id, name))
        self.company_id = company_id

    def __repr__(self):
        return "company_ref(%s, %r)" % (self.company_id, self.xmlid)


# --- namespace con el que se evalúan los expected_*.py --------------------

def ref(xmlid):
    return Ref(xmlid)


def company_ref(company_id, xmlid):
    return CompanyRef(company_id, xmlid)


NAMESPACE = {
    "ref": ref,
    "company_ref": company_ref,
}


# --- forma del spec: {campo: esperado} --------------------------------------

def parse_spec(spec, key, xmlid):
    """El spec de un registro es {campo: valor esperado post-migración}. Las
    claves 'before'/'after' del diseño anterior (ADR 0006) se rechazan
    explícitamente: el before ya no existe y aceptarlo en silencio dejaría un
    dict que parece contrato sin serlo."""
    if not isinstance(spec, dict):
        raise ValueError("%s: %s: spec debe ser un dict, recibí %r" % (key, xmlid, spec))
    legacy = {"before", "after"} & set(spec)
    if legacy:
        raise ValueError(
            "%s: %s: el formato before/after quedó sin efecto (ADR 0007) — "
            "declará solo el estado esperado post-migración: {campo: valor}"
            % (key, xmlid)
        )
    return spec


# --- descubrimiento y carga -------------------------------------------------

def iter_expected_files(root):
    """<root>/<modulo>/tests/expected_*.py, orden estable. root es el repo
    odoo-upgrade."""
    if not os.path.isdir(root):
        return
    for mod_dir in sorted(os.listdir(root)):
        tests_dir = os.path.join(root, mod_dir, "tests")
        if not os.path.isdir(tests_dir):
            continue
        for fname in sorted(os.listdir(tests_dir)):
            if fname.startswith("expected_") and fname.endswith(".py"):
                yield mod_dir, fname, os.path.join(tests_dir, fname)


def load_expected(path):
    """Evalúa un expected_*.py con las primitivas ya en el namespace: el
    archivo queda 100% declarativo, sin imports."""
    ns = dict(NAMESPACE)
    with open(path) as f:
        code = f.read()
    exec(compile(code, path, "exec"), ns)  # noqa: S102 — archivo del repo, no input externo
    expected = ns.get("EXPECTED")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("%s no define un EXPECTED no vacío" % path)
    return expected


def data_key(mod_dir, fname):
    """Identificador del archivo declarativo en los reportes del runner."""
    return "declarative.%s.%s" % (mod_dir, fname[:-3])
