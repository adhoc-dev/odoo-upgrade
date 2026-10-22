# Primitivas del formato declarativo de tests de migración.
# Diseño: actua-20-project/decisions/0007-el-check-es-el-unico-carril.md
#
# Un test de migración es un archivo <modulo>/tests/expected_*.py que define
#     EXPECTED = { <modelo>: { ref(...): {<campo>: <valor esperado>} } }
# donde el valor esperado es el que debe quedar DESPUÉS de la migración. No hay
# contraparte "before": nada se verifica sobre la base fuente (ADR 0007).
# De un campo relacional el valor esperado se declara con los mismos ref(): uno
# para un m2o, una lista para un x2m, [] o None para vacío.
# Este módulo provee las primitivas con las que se escribe ese dict y el
# descubrimiento/parseo que usa check_expected.py.
#
# Sin dependencias de Odoo: importable desde cualquier runner y desde
# odoo shell por igual.

import os
import re


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


def split_field(field, key, xmlid):
    """El campo declarado y el idioma en que se lee: 'name@es_AR' -> ('name',
    'es_AR'), 'name' -> ('name', None). Sirve para verificar una traducción:
    sin idioma el runner lee el campo sin lang en el contexto. Que el idioma esté
    activo y que el campo sea traducible lo cruza el runner, que tiene Odoo."""
    name, sep, lang = field.partition("@")
    if not sep:
        return field, None
    if not name or not lang:
        raise ValueError(
            "%s: %s: %r — un campo en un idioma se declara 'campo@idioma', "
            "por ejemplo 'name@es_AR'" % (key, xmlid, field)
        )
    return name, lang


def parse_expected_value(want, key, xmlid, field):
    """Clasifica el valor declarado para un campo mirando SOLO su forma: acá
    no hay Odoo, así que contra el tipo real del campo lo cruza el runner.

    Devuelve ('refs', [Ref, ...]) cuando el valor se declaró con
    ref()/company_ref() —uno solo, o una lista para un x2m— y ('scalar', want)
    para todo lo demás. El vacío (None, []) sale como escalar: qué significa
    vacío depende del campo, y eso lo sabe el runner.

    Los ids crudos NO son una forma válida de declarar un relacional, pero eso
    tampoco se decide acá: sin el campo a la vista, un int puede ser un entero
    esperado perfectamente legítimo."""
    if isinstance(want, Ref):
        return "refs", [want]
    if isinstance(want, (list, tuple, set, frozenset)):
        items = list(want)
        refs = [v for v in items if isinstance(v, Ref)]
        if not refs:
            return "scalar", want
        if len(refs) != len(items):
            raise ValueError(
                "%s: %s: %s mezcla ref() con valores sueltos (%r) — un x2m se "
                "declara con refs, o vacío ([] / None)" % (key, xmlid, field, want)
            )
        xmlids = [r.xmlid for r in refs]
        dupes = sorted({x for x in xmlids if xmlids.count(x) > 1})
        if dupes:
            raise ValueError(
                "%s: %s: %s repite %s — lo esperado de un x2m es el conjunto "
                "de registros vinculados, y un vínculo no se repite"
                % (key, xmlid, field, ", ".join(dupes))
            )
        return "refs", refs
    return "scalar", want


# --- descubrimiento y carga -------------------------------------------------

def iter_expected_files(root):
    """<root>/<modulo>/tests/expected_*.py, orden estable. root es la carpeta
    modules/ del repo odoo-upgrade."""
    if not os.path.isdir(root):
        return
    for mod_dir in sorted(os.listdir(root)):
        tests_dir = os.path.join(root, mod_dir, "tests")
        if not os.path.isdir(tests_dir):
            continue
        for fname in sorted(os.listdir(tests_dir)):
            if fname.startswith("expected_") and fname.endswith(".py"):
                yield mod_dir, fname, os.path.join(tests_dir, fname)


def version_tag(serie):
    """Sufijo de expected_<ver>.py para la serie de Odoo que corre el check:
    '19.0' -> '190', 'saas~18.4' -> '184'. El check corre después del -u, así
    que la serie que corre es la versión destino del salto."""
    return serie.split("~")[-1].replace(".", "")


def expected_version(fname):
    """El <ver> de expected_<ver>.py (tres dígitos), o None si el nombre no
    dice el salto."""
    match = re.fullmatch(r"expected_(\d{3})\.py", fname)
    return match.group(1) if match else None


def split_by_version(files, tag):
    """Reparte lo que devuelve iter_expected_files en (del salto, de otros
    saltos, sin versión en el nombre). El porqué, en el README."""
    current, others, unnamed = [], [], []
    for item in files:
        ver = expected_version(item[1])
        if ver is None:
            unnamed.append(item)
        elif ver == tag:
            current.append(item)
        else:
            others.append(item)
    return current, others, unnamed


def missing_jump(current, others):
    """Qué pasa si el salto no tiene sus expected: None si los tiene,
    'notice' si hay de otros saltos (salto recién abierto), 'fail' si no hay
    ninguno."""
    if current:
        return None
    return "notice" if others else "fail"


class Declaration:
    """Lo que declara un expected_<ver>.py: qué verifica (EXPECTED), qué
    scripts de 0.0.0 cubre ese EXPECTED (SCRIPTS) y qué queda sin check y por
    qué (NO_CHECK). El porqué de cada uno, en el README."""

    def __init__(self, expected=None, no_check=None, scripts=None):
        self.expected = expected
        self.no_check = no_check
        self.scripts = scripts

    @property
    def whole_no_check(self):
        """True si NO_CHECK es un motivo para todo el archivo."""
        return isinstance(self.no_check, str)


def _check_reason(reason, path, what):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("%s: %s tiene que decir el motivo, recibí %r" % (path, what, reason))


def load_declaration(path):
    """Evalúa un expected_*.py con las primitivas ya en el namespace: el
    archivo queda 100% declarativo, sin imports."""
    ns = dict(NAMESPACE)
    with open(path) as f:
        code = f.read()
    exec(compile(code, path, "exec"), ns)  # noqa: S102 — archivo del repo, no input externo
    expected = ns.get("EXPECTED")
    no_check = ns.get("NO_CHECK")
    scripts = ns.get("SCRIPTS")

    if expected is not None and (not isinstance(expected, dict) or not expected):
        raise ValueError("%s: EXPECTED tiene que ser un dict no vacío" % path)
    if expected is None and no_check is None:
        raise ValueError("%s no define un EXPECTED no vacío ni un NO_CHECK" % path)
    if isinstance(no_check, dict):
        if not no_check:
            raise ValueError("%s: NO_CHECK vacío — sacalo, o nombrá los scripts" % path)
        for script, reason in no_check.items():
            _check_reason(reason, path, "NO_CHECK[%r]" % script)
    elif no_check is not None:
        _check_reason(no_check, path, "NO_CHECK")
        if expected is not None:
            raise ValueError(
                "%s: NO_CHECK = <motivo> dice que el archivo no verifica nada, y "
                "trae un EXPECTED — para un script de 0.0.0 sin check, "
                "NO_CHECK = {<script>: <motivo>}" % path)
    if scripts is not None:
        if expected is None:
            raise ValueError("%s: SCRIPTS nombra lo que verifica el EXPECTED, y no hay EXPECTED" % path)
        if (not isinstance(scripts, (list, tuple)) or not scripts
                or not all(isinstance(x, str) for x in scripts)):
            raise ValueError("%s: SCRIPTS tiene que ser una lista de nombres de script" % path)
        dupes = sorted({x for x in scripts if list(scripts).count(x) > 1})
        if dupes:
            raise ValueError("%s: SCRIPTS repite %s" % (path, ", ".join(dupes)))
        both = sorted(set(scripts) & set(no_check if isinstance(no_check, dict) else ()))
        if both:
            raise ValueError("%s: %s está en SCRIPTS y en NO_CHECK" % (path, ", ".join(both)))
    return Declaration(expected, no_check, scripts)


# --- qué script tiene su check (ADR 0037 de actua-20) -----------------------

# Desde este salto todo script de modules/ lleva su check. Los saltos
# anteriores tienen scripts sin check, de antes de la regla.
FIRST_ENFORCED = 200
ALWAYS = "0.0.0"


def enforced(tag):
    return int(tag) >= FIRST_ENFORCED


def folder_tag(name):
    """El salto de una carpeta de versión de un módulo: '20.0.1.0.0' -> '200'.
    None para 0.0.0 (corre en todos los saltos) y para lo que no es una
    versión (tests/)."""
    match = re.fullmatch(r"([1-9]\d*)\.0(?:\.\d+)+", name)
    return "%s0" % match.group(1) if match else None


def _module_dirs(root):
    if not os.path.isdir(root):
        return
    for mod in sorted(os.listdir(root)):
        mod_dir = os.path.join(root, mod)
        if os.path.isdir(mod_dir):
            yield mod, mod_dir


def enforced_tags(root):
    """Los saltos que se controlan: el primero que se exige y cualquier otro
    posterior que ya tenga carpetas o expected en el repo."""
    tags = {str(FIRST_ENFORCED)}
    for _mod, mod_dir in _module_dirs(root):
        for name in os.listdir(mod_dir):
            tag = folder_tag(name)
            if tag:
                tags.add(tag)
    for _mod, fname, _path in iter_expected_files(root):
        tag = expected_version(fname)
        if tag:
            tags.add(tag)
    return sorted((t for t in tags if enforced(t)), key=int)


def missing_checks(root, tag):
    """Lo que corre en el salto `tag` sin su check, como mensajes. root es la
    carpeta modules/. Una carpeta de versión la cubre el expected_<tag>.py del
    módulo; un script de 0.0.0 tiene que estar nombrado en ese archivo, en
    SCRIPTS o en NO_CHECK."""
    problems = []
    fname = "expected_%s.py" % tag
    for mod, mod_dir in _module_dirs(root):
        own = sorted(n for n in os.listdir(mod_dir) if folder_tag(n) == tag)
        always_dir = os.path.join(mod_dir, ALWAYS)
        always = sorted(
            n for n in os.listdir(always_dir) if n.endswith(".py")
        ) if os.path.isdir(always_dir) else []
        if not own and not always:
            continue
        where = "modules/%s/tests/%s" % (mod, fname)
        path = os.path.join(mod_dir, "tests", fname)
        if not os.path.isfile(path):
            for name in own:
                problems.append(
                    "modules/%s/%s/: sin check — falta %s, con su EXPECTED o con "
                    "NO_CHECK = \"<motivo>\"" % (mod, name, where))
            for name in always:
                problems.append(
                    "modules/%s/%s/%s: sin check en el salto a %s — falta %s, que "
                    "lo nombre en SCRIPTS o en NO_CHECK" % (mod, ALWAYS, name, tag, where))
            continue
        try:
            decl = load_declaration(path)
        except Exception as exc:
            problems.append("%s: ilegible (%s)" % (where, exc))
            continue
        if decl.whole_no_check:
            continue
        if own and decl.expected is None:
            problems.append(
                "%s: no trae EXPECTED ni NO_CHECK = \"<motivo>\" para %s"
                % (where, ", ".join("modules/%s/%s/" % (mod, n) for n in own)))
        named = set(decl.scripts or ()) | set(decl.no_check or ())
        for name in sorted(named - set(always)):
            problems.append(
                "%s: nombra %s, que no está en modules/%s/%s/ — ¿se renombró o "
                "se borró?" % (where, name, mod, ALWAYS))
        for name in always:
            if name not in named:
                problems.append(
                    "modules/%s/%s/%s: sin check en el salto a %s — sumalo a SCRIPTS "
                    "de %s si su EXPECTED lo verifica, o a NO_CHECK con el motivo"
                    % (mod, ALWAYS, name, tag, where))
    return problems


def data_key(mod_dir, fname):
    """Identificador del archivo declarativo en los reportes del runner."""
    return "declarative.%s.%s" % (mod_dir, fname[:-3])
