# ADHOC odoo-upgrade

Manejamos todos los scripts de actualizacion este unico branch.
Para que versiones aplica se gestiona utilizando las versiones correspondientes en cada modulo

## Estructura

- `modules/`: lo que Odoo lee como `--upgrade-path`, un script por módulo y versión
  (`modules/<modulo>/<version>/pre|post|end-*.py`). Solo módulos.
- `scripts/pre_odoo/`: corre sobre la base de origen antes de mandarla a Odoo.
- `scripts/pre_upgrade/`: corre antes de cargar `base`, con `--pre-upgrade-scripts`.
- `lib/oba/`: los helpers de los scripts. Se importan como `oba`, con `lib/` en el
  `PYTHONPATH` de quien corre los scripts.
- `tests/pre_odu/` y `tests/post_odu/`: la siembra de la base de prueba y el check
  declarativo de runbot.

La documentación de este proyecto la llevamos [acá]( https://docs.google.com/document/d/1Qm5fSkjcA_j8QfUO7frL4lgKQ4LG3AN8we2Aw8_g4p8/edit#)
