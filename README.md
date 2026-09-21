# ADHOC odoo-upgrade

Manejamos todos los scripts de actualizacion este unico branch.
Para que versiones aplica se gestiona utilizando las versiones correspondientes en cada modulo

La documentación de este proyecto la llevamos [acá]( https://docs.google.com/document/d/1Qm5fSkjcA_j8QfUO7frL4lgKQ4LG3AN8we2Aw8_g4p8/edit#)

## Los scripts de `pre_upgrade_scripts/` se corren más de una vez

Un `-u` que falla se retoma sobre la misma base: el provider vuelve a lanzar el pase con
los módulos que quedaron sin actualizar, y los módulos que ya pasaron no se tocan. Los
scripts de `pre_upgrade_scripts/` —`always/` y los de cada salto— no van atados a la
versión de ningún módulo, así que vuelven a correr enteros en cada corrida, sobre datos
que la corrida anterior ya migró. Las reglas:

- **Correr de nuevo no puede fallar.** Cada uno se guarda con `util.table_exists` /
  `util.column_exists` o con un `WHERE` que no encuentre nada la segunda vez.
- **Un respaldo se hace una sola vez.** Si la copia ya está, se deja: los datos vigentes
  pueden ser los que migró el intento anterior, y rehacerla desde ahí pisa el original.
- **Un respaldo se consume una sola vez.** Lo que repara con él ya quedó commiteado, así
  que la corrida retomada no lo tiene que rehacer: sin la tabla, el script no hace nada y
  lo dice en el log.
- **No se borra lo que escribió la corrida anterior.** Los módulos que ya pasaron no
  vuelven a escribirlo.
- **Lo que apaga o borra nuestro propio `-u` se queda como está.** Una corrida retomada no
  lo revierte: el módulo que lo hizo ya no vuelve a correr para rehacerlo.

Los scripts de migración de cada módulo (`<módulo>/<versión>/`) no necesitan esto: si el
módulo no llegó a `installed`, su transacción se revirtió entera y vuelven a correr desde
cero.

La segunda vuelta de los scripts que tocan datos que no se pueden rehacer está cubierta
por `pre_upgrade_scripts/tests/test_resumed_run.py`, que se corre a mano:

    /home/odoo/venv/bin/python pre_upgrade_scripts/tests/test_resumed_run.py
