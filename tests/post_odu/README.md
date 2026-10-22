# tests/post_odu — tests de migración declarativos

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
2. **la siembra de [`tests/pre_odu/`](../pre_odu/README.md)** (este
   mismo repo), solo para los casos que esa data no contempla. Un caso nuevo
   es siempre **un solo PR**, lleve o no data nueva.

`expected_lib.py` trae las primitivas (`ref` / `company_ref`) y el
descubrimiento de `<modulo>/tests/expected_*.py`.

## Cada salto corre solo sus expected

`expected_<ver>.py` verifica el estado que deja el salto a esa versión:
`expected_190.py` es el de 18→19. El check corre después del `-u`, así que toma
la versión de la serie de Odoo que lo ejecuta (`19.0` → `190`, `20.0` → `200`) y
corre solo esos. Los de otros saltos salen en el log como `SKIP`: un expected de
un salto anterior mira campos que el siguiente puede renombrar o sacar, y su FAIL
no diría nada del salto que se prueba.

## Dónde vive cada pieza

| Pieza | Dónde | Qué es |
|---|---|---|
| `check_expected.py` | acá | el runner: corre en `odoo shell` y decide el exit code |
| `expected_lib.py` | acá | el formato: primitivas, validación de lo declarado y descubrimiento, sin Odoo |
| `test_expected_lib.py` | acá | el arnés de `expected_lib.py` |
| `missing_checks.py` | acá | el control de scripts sin check que corre el job de GitHub |
| `expected_*.py` | `modules/<modulo>/tests/` | la data: un archivo por módulo y versión |
| la siembra | `tests/pre_odu/` | los registros que la data de prueba no trae |

`expected_lib.py` no va a `lib/oba`: `lib/oba` es lo que importan los scripts
durante la actualización, y nada de este formato lo usa un script. Hoy sus
únicos consumidores son el runner y su arnés. Se muda cuando aparezca un
consumidor fuera de `post_odu`, y a un subpaquete propio, no a `oba` directo.

El runner tampoco se mueve solo: el step 31 de runbot (`test-migration-check`)
busca `tests/post_odu/check_expected.py` y, si el checkout de `odoo-upgrade` no
lo trae, termina el build en `ko`. Cambiarle el path pide tocar el step en el
mismo momento.

## Campos relacionales: el valor también se declara con `ref()`

Un m2o o un x2m se declara con las mismas primitivas que la clave, así el
expected no depende de ids —que no son estables entre bases— ni queda limitado
a "el campo tiene que estar vacío":

> El ejemplo de abajo es de `route_line_test`, el módulo de prueba del remapeo
> m2o → m2m, y **todavía no está en master**: vive en una rama de trabajo, así
> que estos xmlids no se encuentran grepeando el repo. El otro ejemplo de este
> README (`po_force_delivered_no`) sí es un caso vivo y sembrado.

```python
EXPECTED = {
    "route.line": {
        # m2o -> m2m: el script tiene que dejar en el m2m nuevo la misma ruta
        # que estaba en el m2o. Parte de route_id = MTO; si acá viene [], la
        # tabla de relación nació vacía y el vínculo se perdió sin error.
        ref("upgrade_prepare_demo.rl_una_ruta"): {
            "route_ids": [ref("stock.route_warehouse0_mto")],
        },
        # Rama de preservación: la línea no tenía ruta y tiene que seguir sin
        # ninguna — que el script no le invente el vínculo por defecto.
        ref("upgrade_prepare_demo.rl_sin_ruta"): {
            "route_ids": [],
        },
    },
}
```

- Un `ref()` suelto para un m2o, una lista para un x2m; vacío es `[]`, `None`
  o el `False` que devuelve el ORM.
- Se compara el **conjunto** de registros vinculados: el orden no se verifica
  (declarar un o2m ordenado queda fuera de este carril).
- `many2one_reference` y `reference` **también quedan afuera**, con su propio
  diagnóstico: el registro apuntado sale de otro campo, así que no hay comodel
  fijo contra el que resolver un `ref()`. El corte es explícito porque
  `Field.relational` los da por no relacionales, y sin él un id crudo en el
  `res_id` de `mail.activity` o de `ir.attachment` pasaba en verde.
- Un **id crudo es FAIL explícito**, no una comparación silenciosa: los ids no
  son estables entre bases y el verde que sacan no significa nada.
- Los refs del lado del valor son **anclas como los de la clave**: si uno no
  resuelve es FAIL con su propio diagnóstico —sin fila en `ir_model_data`,
  xmlid colgado, o registrado bajo otro modelo que el que apunta el campo—, y
  no un `esperaba X, obtuvo Y` que se leería como culpa del migration script.
- El diff se imprime con el xmlid al lado del id (`[12 (stock.route_mto)]`).

## Traducciones: el campo se declara `campo@idioma`

Sin idioma, el runner lee el campo sin `lang` en el contexto. Para verificar una
traducción, la clave lleva el idioma después de una `@`:

```python
EXPECTED = {
    "ir.ui.menu": {
        # El script recarga las traducciones con overwrite: el término editado a
        # mano en es_AR vuelve al del .po. Si sigue editado, no recargó.
        ref("sale.sale_menu_root"): {
            "name@es_AR": "Ventas",
        },
    },
}
```

- Solo aplica a un campo traducible: en otro es FAIL de lo declarado.
- El idioma tiene que estar **activo** en la base: si no, el ORM leería el campo
  en `en_US` y el assert compararía otra cosa. También es FAIL de lo declarado.

## Anti-falso-verde (regla del runner, no de cada test)

- ningún `expected_<ver>.py` descubierto ⇒ FAIL
- `expected_*.py` sin la versión en el nombre (tres dígitos) ⇒ FAIL
- expected ilegible ⇒ FAIL
- `ref` que no resuelve o registro desaparecido ⇒ **FAIL**
- archivo con 0 asserts ⇒ FAIL
- desde el salto a 20, un script sin su check ⇒ FAIL (ver abajo)

Un salto sin sus `expected_<ver>.py`, pero con los de otros saltos, no es FAIL:
el check sale verde con un `AVISO - sin expected_<ver>.py ...` en el log. Es el
estado de un salto recién abierto (la 20, hoy), y dejarlo en rojo pondría en ko
todos sus builds.

Nunca hay skip silencioso — la diferencia deliberada con el carril nativo de
`odoo.upgrade.testing`, donde un `check` sin su key en `upgrade_test_data`
loguea INFO y pasa en verde.

Sobre el registro ausente: es FAIL **siempre**, y el diagnóstico deja las dos
hipótesis abiertas —lo borró la actualización, o nunca estuvo cargado en la base
fuente—. Sin gate previo no se pueden distinguir desde acá, y no hay forma de
declarar una ausencia como esperada: un caso donde el registro debe desaparecer
se verifica por otra vía.

## Todo script lleva su check, desde el salto a 20

El ADR 0037 de actua-20 pide que todo script de `modules/` vaya con su check, y
desde el salto a 20 lo controlan dos lugares con la misma función
(`missing_checks` de `expected_lib.py`):

- el job `missing-checks` de `.github/workflows/layout.yml`, en cada push y sin
  levantar Odoo (`python3 tests/post_odu/missing_checks.py`), para todos los
  saltos desde el 20;
- `check_expected.py` en runbot, para el salto que prueba.

Qué cuenta como cubierto:

- **Una carpeta de versión** `modules/<modulo>/20.0.x/`: la cubre
  `modules/<modulo>/tests/expected_200.py`, con su `EXPECTED` o con
  `NO_CHECK = "<motivo>"`.
- **Un script de `0.0.0`**, que corre en todos los saltos: cada uno tiene que
  estar nombrado en el `expected_<ver>.py` de su módulo, en `SCRIPTS` (los que
  verifica el `EXPECTED`) o en `NO_CHECK = {"<script>": "<motivo>"}`. Un nombre
  que ya no está en `0.0.0` también es FAIL: si un script se renombra, su check
  no queda apuntando a nada sin aviso.

```python
# modules/base/tests/expected_200.py
SCRIPTS = ["end-110-reload_translations.py"]
NO_CHECK = {
    "pre-0-disable-check-views.py": "Parchea un metodo en memoria mientras corre el -u: ...",
}
```

`NO_CHECK` parte de una necesidad concreta: el script toca algo que no tiene
sentido o no se puede verificar con este carril, por ejemplo el arch de una
vista o un parche en memoria (la tabla de la skill
`odoo-upgrade-declarative-checks`). Siempre lleva el motivo. Que falte tiempo
para escribir el check no es un motivo; la excepción son los scripts de
`base/0.0.0` anteriores a la regla, que quedan como pendientes. El runner lo muestra
como `SIN CHECK - <archivo>: <motivo>` en el log del build. Los saltos anteriores
al 20 no se controlan: tienen scripts de antes de la regla.

Fuera de este control: `scripts/pre_odoo/` y `scripts/pre_upgrade/`, que corren
antes del `-u` y no tienen este carril.

## Correrlo (local, sobre una base post-ODU restaurada)

```bash
# el -u de siempre (ningún flag extra: no hay prepare)
odoo -d <db> -u all --stop-after-init --max-cron-threads=0 \
  --upgrade-path=<upgrade-util>/src,<este-repo>/modules

# check post-migración
echo 'exec(open("<repo>/tests/post_odu/check_expected.py").read())' \
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
- Valores esperados: escalares y relacionales (ver arriba).
- La parte de `expected_lib.py` que no necesita Odoo tiene arnés propio:
  `python3 tests/post_odu/test_expected_lib.py` (sin base ni
  infra). Lo que sí necesita un `env` —que un `ref()` resuelva, que un id
  crudo FAILee— se prueba sobre una base viva.
- Verificar data **orgánica** de la base (registros sin xmlid, correlacionando
  valor viejo → nuevo) requiere una ventana pre-`-u`, que es justamente lo que
  este diseño evita: ese carril queda fuera, y el escape hatch imperativo es
  `prepare_post_odu.py` (PR #172).
- Convive con `odoo.upgrade.testing` para `IntegrityCase` globales.
