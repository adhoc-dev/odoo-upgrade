# Check de los tests declarativos — el único carril de verificación (ADR 0007).
# Corre DESPUÉS del -u, en odoo shell:
#   echo 'exec(open("<repo>/testing_post_odu/check_expected.py").read())' \
#     | odoo shell -d <db> --no-http
# (via exec(): el shell de odoo ejecuta stdin línea a línea y rompe scripts
# multi-línea; os._exit al final porque el InteractiveConsole traga SystemExit)
# Diseño: actua-20-project/decisions/0007-el-check-es-el-unico-carril.md
#
# No se verifica nada sobre la base fuente: la base que recibimos se da por
# buena, es la base candidata que ya preparamos con su data. Acá se chequea
# una sola cosa: que lo que pasó por el migration script salga como debe.
#
# Reglas anti-falso-verde (nativas del runner, nadie las re-implementa por test):
#   - 0 archivos expected descubiertos            => FAIL
#   - expected ilegible                           => FAIL
#   - ref que no resuelve / registro desaparecido => FAIL (ver abajo)
#   - archivo con 0 asserts                       => FAIL
#
# Un ref ausente es FAIL siempre, del lado de la clave y del lado del valor. El
# diagnóstico distingue las formas: sin fila en ir_model_data (purga del xmlid,
# o siembra que nunca corrió sobre la base fuente), xmlid colgado (la fila está
# pero el registro no — borrado SQL sin limpiar ir_model_data), y xmlid
# registrado bajo otro modelo (el ref apunta a donde no es). Sin gate previo no
# se puede afinar más desde acá — pero un verde tampoco puede salir de un
# registro que no está.
#
# Campos relacionales: el valor esperado se declara con ref(), igual que la
# clave — uno para un m2o, una lista para un x2m, [] o None para vacío. Se
# compara como CONJUNTO de registros vinculados: el orden no se verifica. Un id
# crudo es FAIL explícito, no una comparación silenciosa: los ids no son
# estables entre bases y el verde que sacan no significa nada.
#
# Sale con exit code 1 si algo falló — INCLUIDO un assert no evaluable: toda
# excepción del loop se captura y se convierte en FAIL de ese assert, y el
# resto se sigue verificando. Antes (medido el 25/08 sobre el shell de 19) un
# typo de campo en un expected abortaba el check ENTERO: exit 1 igual (el
# shell propaga la excepción), pero sin resumen, sin verificar los asserts
# restantes y con un traceback crudo como único diagnóstico.

import os
import sys

# root del repo odoo-upgrade: exec() no define __file__, así que se resuelve
# por env o por los paths conocidos (runbot / stack local de dev)
_CANDIDATES = [
    os.environ.get("ODOO_UPGRADE_ROOT"),
    "/data/build/ingadhoc-odoo-upgrade",
    "/home/odoo/custom/repositories/odoo-upgrade",
]
ROOT = next((p for p in _CANDIDATES if p and os.path.isdir(p)), None)
if ROOT is None:
    print("=== check declarativo: FAIL — no encuentro el repo odoo-upgrade "
          "(seteá ODOO_UPGRADE_ROOT) ===")
    sys.stdout.flush()
    os._exit(1)

sys.path.insert(0, os.path.join(ROOT, "testing_post_odu"))
import expected_lib as X  # noqa: E402

cr = env.cr  # noqa: F821 — `env` es global del odoo shell

failures, passed = [], 0


class _DeclError(Exception):
    """Problema en lo declarado, o en el ancla del valor esperado — no en el
    dato migrado. Se reporta con su propio mensaje en vez del genérico de
    'no evaluable', que mandaría a buscar un typo donde no lo hay."""


def _norm(value):
    """Normaliza el valor de un campo NO relacional para comparar contra lo
    declarado: el False del ORM (selection/char vacío) -> None. Los
    relacionales no pasan por acá: se comparan por conjunto de ids."""
    if value is False or value is None:
        return None
    return value


def _resolve_ref(xmlid, model):
    """(res_id, problema). problema es None, 'missing' (no hay fila en
    ir_model_data) o 'model:<modelo>' (el xmlid existe, pero registrado bajo
    otro modelo — el error típico de un ref del lado del valor).

    Una fila como máximo: ir_model_data tiene índice único sobre
    (module, name) — `_module_name_uniq_index` en base/models/ir_model.py."""
    module, name = xmlid.split(".", 1)
    cr.execute(
        "SELECT model, res_id FROM ir_model_data WHERE module = %s AND name = %s",
        (module, name),
    )
    row = cr.fetchone()
    if not row:
        return None, "missing"
    row_model, res_id = row
    if row_model == model:
        return res_id, None
    return None, "model:%s" % row_model


def _wanted_ids(refs, comodel, key, xmlid, field):
    """Ids de los refs declarados del lado del valor. Uno que no resuelve es
    _DeclError, no un mismatch: si saliera como 'esperaba X, obtuvo Y' se
    leería como culpa del migration script, y el problema es el ancla."""
    ids = set()
    for r in refs:
        res_id, problem = _resolve_ref(r.xmlid, comodel)
        if problem == "missing":
            raise _DeclError(
                "%s: %s: %s: el ref esperado %s no tiene fila en ir_model_data "
                "para %s — la purgó la actualización, o la siembra nunca corrió "
                "sobre la base fuente" % (key, xmlid, field, r.xmlid, comodel))
        if problem:
            raise _DeclError(
                "%s: %s: %s: el ref esperado %s no es de %s (que es a donde "
                "apunta el campo); ir_model_data lo tiene bajo %s"
                % (key, xmlid, field, r.xmlid, comodel, problem.split(":", 1)[1]))
        if not env[comodel].browse(res_id).exists():  # noqa: F821
            raise _DeclError(
                "%s: %s: %s: el ref esperado %s (%s) está colgado — "
                "ir_model_data apunta al id %s pero el registro no existe"
                % (key, xmlid, field, r.xmlid, comodel, res_id))
        ids.add(res_id)
    return ids


def _label_ids(ids, model):
    """Ids con su xmlid cuando lo tienen: un id pelado no le dice nada a quien
    lee el log del build."""
    if not ids:
        return "[]"
    # ORDER BY: un registro puede tener más de un xmlid, y sin orden el
    # setdefault se queda con el que la base devuelva primero — la etiqueta
    # cambiaría entre corridas, que es ruido en un log que se compara entre builds.
    cr.execute(
        "SELECT res_id, module || '.' || name FROM ir_model_data "
        "WHERE model = %s AND res_id IN %s ORDER BY module, name",
        (model, tuple(ids)))
    known = {}
    for res_id, xmlid in cr.fetchall():
        known.setdefault(res_id, xmlid)
    return "[%s]" % ", ".join(
        "%s (%s)" % (i, known[i]) if i in known else str(i) for i in sorted(ids))


def _check_field(record, field, want, key, xmlid):
    """None si el assert pasa, o el mensaje del FAIL. Levanta _DeclError si el
    problema está en lo declarado; cualquier otra excepción (un compute que
    revienta, un typo de campo) se deja escapar y la reporta el llamador."""
    try:
        kind, declared = X.parse_expected_value(want, key, xmlid, field)
    except ValueError as exc:
        raise _DeclError(str(exc))

    fdef = record._fields[field]  # KeyError de un typo: lo agarra el llamador
    # `relational` es False para many2one_reference y reference, que igual
    # apuntan a un registro. Sin este corte los dos se colaban por la rama
    # escalar: en un many2one_reference (el res_id de mail.activity, de
    # ir.attachment) el id crudo se comparaba contra el id crudo y PASABA EN
    # VERDE, que es justo lo que este carril prohibe; y en un reference, que se
    # lee como recordset, la comparación fallaba siempre. Los dos quedan fuera
    # del carril, dicho con su diagnóstico.
    if fdef.type in ("many2one_reference", "reference"):
        raise _DeclError(
            "%s: %s: %s es %s, y este carril no lo alcanza: el registro "
            "apuntado sale de otro campo, así que no hay comodel fijo contra "
            "el que resolver un ref(). Verificalo en un test propio del módulo"
            % (key, xmlid, field, fdef.type))
    if not getattr(fdef, "relational", False):
        if kind == "refs":
            raise _DeclError(
                "%s: %s: %s no es relacional (%s) — ref() del lado del valor "
                "solo aplica a m2o/o2m/m2m" % (key, xmlid, field, fdef.type))
        got = _norm(record[field])
        if got == _norm(want):
            return None
        return "%s: %s: %s esperaba %r, obtuvo %r" % (key, xmlid, field, want, got)

    comodel = fdef.comodel_name
    if kind == "refs":
        want_ids = _wanted_ids(declared, comodel, key, xmlid, field)
    elif declared is None or declared is False or (
        isinstance(declared, (list, tuple, set, frozenset)) and not declared
    ):
        # vacío: el None y el False históricos (el ORM devuelve False) y el []
        # explícito. False tiene que seguir pasando: es lo que escribían los
        # expected escritos antes de este carril.
        want_ids = set()
    else:
        raise _DeclError(
            "%s: %s: %s es %s a %s y se declaró %r — un relacional se declara "
            "con ref('modulo.nombre') (lista si es x2m) o vacío con [] / None, "
            "nunca con ids crudos: no son estables entre bases"
            % (key, xmlid, field, fdef.type, comodel, declared))

    got_ids = set(record[field].ids)
    if got_ids == want_ids:
        return None
    return ("%s: %s: %s esperaba %s, obtuvo %s"
            % (key, xmlid, field,
               _label_ids(want_ids, comodel), _label_ids(got_ids, comodel)))


# Cinturón global: ninguna excepción escapa de este bloque — el resumen y el
# os._exit de abajo corren siempre, así el log del step termina en la línea
# "=== check declarativo: ..." también cuando el runner mismo falla.
try:
    files = list(X.iter_expected_files(ROOT))
    if not files:
        failures.append("0 archivos expected_*.py bajo %s — nada se verificó" % ROOT)

    for mod_dir, fname, path in files:
        key = X.data_key(mod_dir, fname)
        try:
            expected = X.load_expected(path)
        except Exception as exc:
            failures.append("%s: expected ilegible (%s)" % (key, exc))
            continue

        file_asserts = 0
        for model, spec in expected.items():
            for selector, fields in spec.items():
                if not isinstance(selector, X.Ref):
                    failures.append(
                        "%s: selector no soportado %r (%s)" % (key, selector, model)
                    )
                    continue
                try:
                    fields = X.parse_spec(fields, key, selector.xmlid)
                except ValueError as exc:
                    failures.append(str(exc))
                    continue
                file_asserts += 1
                res_id, problem = _resolve_ref(selector.xmlid, model)
                if problem == "missing":
                    failures.append(
                        "%s: ref %s (%s) sin fila en ir_model_data — la purgó "
                        "la actualización, o la siembra nunca corrió sobre la "
                        "base fuente" % (key, selector.xmlid, model)
                    )
                    continue
                if problem:
                    failures.append(
                        "%s: ref %s no es de %s — ir_model_data lo tiene bajo "
                        "%s: el expected lo declaró en el modelo equivocado"
                        % (key, selector.xmlid, model, problem.split(":", 1)[1])
                    )
                    continue
                record = env[model].browse(res_id).exists()  # noqa: F821
                if not record:
                    failures.append(
                        "%s: ref %s (%s) colgado — ir_model_data apunta al id "
                        "%s pero el registro no existe: lo borró la "
                        "actualización (borrado SQL sin limpiar ir_model_data)"
                        % (key, selector.xmlid, model, res_id)
                    )
                    continue
                for field, want in fields.items():
                    # try por campo: nada de un assert puede abortar el runner.
                    # Un problema de lo DECLARADO (ref del valor que no
                    # resuelve, id crudo en un relacional, ref en un campo que
                    # no lo es) trae su propio mensaje; el resto —typo de campo
                    # (KeyError), compute que revienta— cae en el genérico.
                    try:
                        problem = _check_field(record, field, want, key, selector.xmlid)
                    except _DeclError as exc:
                        failures.append(str(exc))
                        continue
                    except Exception as exc:
                        failures.append(
                            "%s: %s: %s no evaluable (%r) — ¿typo en el "
                            "expected, o campo no comparable?"
                            % (key, selector.xmlid, field, exc)
                        )
                        continue
                    if problem:
                        failures.append(problem)
                    else:
                        passed += 1

        if not file_asserts:
            failures.append("%s: 0 asserts — el archivo no verifica nada" % key)
except Exception as exc:
    failures.append("crash del runner: %r — nada de lo posterior se verificó" % (exc,))

print("")
print("=== check declarativo: %s OK, %s FAIL ===" % (passed, len(failures)))
for f in failures:
    print("FAIL - %s" % f)

# os._exit no flushea buffers y stdout es un pipe: sin esto el resumen se pierde
sys.stdout.flush()
sys.stderr.flush()
os._exit(1 if failures else 0)
