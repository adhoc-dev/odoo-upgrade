# testing_post_odu — tests de migración declarativos

Un test de migración acá es **un dict de estado esperado**, no una clase:

```python
# <modulo>/tests/expected_190.py — sin imports, 100% declarativo
EXPECTED = {
    "purchase.order": {
        # Rama 'no': el valor dejó de existir en el selection de 19, así que el
        # script tiene que vaciarlo. Parte de force_delivered_status = 'no'.
        ref("upgrade_prepare_demo.po_force_delivered_no"): {
            "force_delivered_status": None,    # lo que debe quedar en 19
        },
    },
}
```

**Cada caso lleva su comentario de qué verifica** — no es adorno: es lo único
que explica por qué ese valor esperado es el correcto. Tres cosas en una o dos
líneas: la **rama** de la transformación que cubre, el **valor de partida**, y
**qué significaría** que el resultado no sea el declarado.

## El check es el único carril

Se declara **solo el estado esperado después de la migración**. Nada se
verifica sobre la base fuente: cuando recibimos la base, se da por bueno que es
la base candidata que ya preparamos con toda su data. Toda la lógica vive del
lado del check, y no hay ninguna corrida contra la versión anterior — así el
flujo depende lo menos posible de ODU (ADR 0007, sucesor del 0006).

| Pieza | Cuándo corre | Qué garantiza |
|---|---|---|
| `check_expected.py` | después del `-u all`, vía `odoo shell` | resuelve cada `ref` y compara los valores declarados. Exit 1 si algo falló. |

De dónde salen los registros que el test referencia con `ref()`:

1. **la data de prueba que traen los módulos instalados** en la base canónica —
   la fuente primaria, no cuesta nada;
2. **la siembra de [`testing_pre_odu/`](../testing_pre_odu/README.md)** (este
   mismo repo), solo para los casos que esa data no contempla. Un caso nuevo
   es siempre **un solo PR**, lleve o no data nueva.

`expected_lib.py` trae las primitivas (`ref` / `company_ref`) y el
descubrimiento de `<modulo>/tests/expected_*.py`.

## Anti-falso-verde (regla del runner, no de cada test)

- 0 archivos descubiertos ⇒ FAIL
- expected ilegible ⇒ FAIL
- `ref` que no resuelve o registro desaparecido ⇒ **FAIL**
- archivo con 0 asserts ⇒ FAIL

Nunca hay skip silencioso — la diferencia deliberada con el carril nativo de
`odoo.upgrade.testing`, donde un `check` sin su key en `upgrade_test_data`
loguea INFO y pasa en verde.

Sobre el registro ausente: es FAIL **siempre**, y el diagnóstico deja las dos
hipótesis abiertas —lo borró la actualización, o nunca estuvo cargado en la base
fuente—. Sin gate previo no se pueden distinguir desde acá, y no hay forma de
declarar una ausencia como esperada: un caso donde el registro debe desaparecer
se verifica por otra vía.

## Correrlo (local, sobre una base post-ODU restaurada)

```bash
# el -u de siempre (ningún flag extra: no hay prepare)
odoo -d <db> -u all --stop-after-init --max-cron-threads=0 \
  --upgrade-path=<upgrade-util>/src,<este-repo>

# check post-migración
echo 'exec(open("<repo>/testing_post_odu/check_expected.py").read())' \
  | odoo shell -d <db> --no-http
# exit code 0 = verde; 1 = al menos un FAIL (impreso con nombre)
```

El check resuelve el root del repo por `ODOO_UPGRADE_ROOT` o por los paths
conocidos (runbot `/data/build/ingadhoc-odoo-upgrade`, stack local
`/home/odoo/custom/repositories/odoo-upgrade`).

## Notas

- Los `expected_*.py` **no** llevan `__init__.py` ni tags: no los levanta el
  test runner de Odoo, los levanta este runner por filesystem.
- Un caso sin comentario es un caso a medias: el dict dice *qué valor* se
  espera, nunca *por qué*. El runner no puede exigirlo (son comentarios de
  Python), así que lo exige el review.
- El formato `{"before": ..., "after": ...}` del diseño anterior (ADR 0006)
  quedó **sin efecto** y el runner lo rechaza con FAIL explícito, en vez de
  ignorar el `before` en silencio.
- Valores esperados: escalares (m2o/x2m: pendiente).
- Verificar data **orgánica** de la base (registros sin xmlid, correlacionando
  valor viejo → nuevo) requiere una ventana pre-`-u`, que es justamente lo que
  este diseño evita: ese carril queda fuera, y el escape hatch imperativo es
  `prepare_post_odu.py` (PR #172).
- Convive con `odoo.upgrade.testing` para `IntegrityCase` globales.
