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
# Un ref ausente es FAIL siempre, con dos hipótesis abiertas: lo borró la
# actualización, o nunca estuvo cargado en la base fuente. Sin gate previo no
# hay forma de distinguirlas desde acá — pero un verde tampoco puede salir de
# un registro que no está.
#
# Sale con exit code 1 si algo falló.

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
            record = env[model].browse(res_id).exists() if res_id else None  # noqa: F821
            if not record:
                failures.append(
                    "%s: ref %s (%s) no existe post-migración — la borró la "
                    "actualización, o no estaba cargada en la base fuente"
                    % (key, selector.xmlid, model)
                )
                continue
            for field, want in fields.items():
                got = _norm(record[field])
                if got == _norm(want):
                    passed += 1
                else:
                    failures.append(
                        "%s: %s: %s esperaba %r, obtuvo %r"
                        % (key, selector.xmlid, field, want, got)
                    )

    if not file_asserts:
        failures.append("%s: 0 asserts — el archivo no verifica nada" % key)

print("")
print("=== check declarativo: %s OK, %s FAIL ===" % (passed, len(failures)))
for f in failures:
    print("FAIL - %s" % f)

# os._exit no flushea buffers y stdout es un pipe: sin esto el resumen se pierde
sys.stdout.flush()
sys.stderr.flush()
os._exit(1 if failures else 0)
