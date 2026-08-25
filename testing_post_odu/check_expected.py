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
# Un ref ausente es FAIL siempre. El diagnóstico distingue las dos formas:
# sin fila en ir_model_data (purga del xmlid, o siembra que nunca corrió
# sobre la base fuente) vs xmlid colgado (la fila está pero el registro no —
# borrado SQL sin limpiar ir_model_data). Sin gate previo no se puede afinar
# más desde acá — pero un verde tampoco puede salir de un registro que no está.
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


def _norm(value):
    """Normaliza el valor ORM para comparar contra lo declarado: False
    (selection/char vacío) -> None; recordset m2o -> id."""
    if value is False or value is None:
        return None
    if hasattr(value, "_name") and hasattr(value, "id"):  # recordset
        return value.id or None
    return value


def _resolve_ref(xmlid, model):
    module, name = xmlid.split(".", 1)
    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s AND model = %s",
        (module, name, model),
    )
    row = cr.fetchone()
    return row[0] if row else None


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
                res_id = _resolve_ref(selector.xmlid, model)
                if not res_id:
                    failures.append(
                        "%s: ref %s (%s) sin fila en ir_model_data — la purgó "
                        "la actualización, o la siembra nunca corrió sobre la "
                        "base fuente" % (key, selector.xmlid, model)
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
                    # try por campo: un typo en el expected (KeyError), un m2m
                    # con 2+ registros (ValueError de _norm) o un compute que
                    # revienta NO pueden abortar el runner — son FAIL de ese
                    # assert y se sigue con el resto.
                    try:
                        got = _norm(record[field])
                    except Exception as exc:
                        failures.append(
                            "%s: %s: %s no evaluable (%r) — ¿typo en el "
                            "expected, o campo no comparable?"
                            % (key, selector.xmlid, field, exc)
                        )
                        continue
                    if got == _norm(want):
                        passed += 1
                    else:
                        failures.append(
                            "%s: %s: %s esperaba %r, obtuvo %r"
                            % (key, selector.xmlid, field, want, got)
                        )

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
