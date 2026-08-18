# testing_pre_odu — siembra de la base de prueba (lado 18, antes de ODU)

Scripts que preparan la **base candidata** antes de que viaje a ODU: curan la
base demo y siembran los registros que después referencian los tests
declarativos de [`testing_post_odu/`](../testing_post_odu/README.md). Absorbe
el repo `upgrade-prepare-demo` (un repo, un bundle, un trigger — ADR 0005 de
actua-20: la data de prueba vive en `odoo-upgrade`).

**Nunca corren para un cliente real.** Ese es el límite con
[`pre_odoo_scripts/`](../pre_odoo_scripts/): aquel carril llega a producción
vía el provider; este existe solo para fabricar la base del pipeline de
testing. La curación de la demo se sacó de `pre_odoo_scripts/` justamente por
ese riesgo (el detach borra `ir_model_data` en bulk).

## Layout y contrato

```
testing_pre_odu/<modulo>/<always|180_190>/NNN-<nombre>.py
```

- Cada script expone `migrate(env)` y debe ser **idempotente** (re-correrlo no
  duplica datos).
- Orden de ejecución: `always/` primero, después el salto (`180_190/`);
  dentro de cada grupo, por nombre de archivo (de ahí el prefijo `NNN-`).
- Los corre el step `run-prepare-demo` de runbot (Fase A) vía `odoo shell`
  sobre la base semilla, antes de `send-db-to-upgrade`.
- Los xmlids sembrados van bajo el módulo virtual **`upgrade_prepare_demo`**
  (vía `_load_records`): ningún addon lo carga, así que `_process_end` nunca
  los reapea. El namespace conserva ese nombre aunque el repo se absorbió —
  está horneado en las bases canónicas existentes y en los `expected_*.py`.

Nada se verifica acá antes del viaje (ADR 0007): si una siembra falla o
falta, lo dice el check post-`-u` como ref ausente.
