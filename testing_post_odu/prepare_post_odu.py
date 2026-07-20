"""Siembra `upgrade_test_data` despues de ODU, para que los `test_check` corran.

El problema que resuelve
------------------------
El framework de tests de upgrade (`odoo/upgrade/testing.py`) guarda el retorno del
`prepare()` en la tabla `upgrade_test_data`, con una key por clase de test. El
`test_check` **solo llama al `check()` si esa key existe**; si no, loguea
`No value found for <key>, skipping check` y el test pasa sin verificar nada. Es el
falso verde que vimos en el build 103446 del e2e.

Correr el `test_prepare` oficial exige tener la base en la version vieja, o sea *antes*
de ODU: cada test nuevo obliga a re-mandar la base y esperar el pase. Este runner saca
ese viaje del loop. Corre como `--pre-upgrade-script`, o sea despues de que Odoo carga el
grafo de `base` y **antes** de actualizar cualquier modulo (`odoo/modules/loading.py`):
en esa ventana el core ya esta en la version nueva pero las columnas de nuestros modulos
todavia estan como las dejo la version vieja, porque ODU no conoce los modulos OBA.

Ahi cada modulo declara su fila de `upgrade_test_data` en
`<modulo>/tests/prepare_post_odu.py`, exponiendo:

    def prepare(cr):
        return {"<archivo_de_test>.<ClaseDeTest>": <valor JSON-serializable>}

    # opcional: las clases de arriba que son IntegrityCase y no UpgradeCase
    INTEGRITY_CASES = {"<archivo_de_test>.<OtraClase>"}

La key final se arma como `<modulo>.tests.<archivo_de_test>.<ClaseDeTest>`, que es lo
mismo que devuelve `UpgradeCommon.key` para esa clase. El `check()` no distingue quien
escribio la fila.

Dos formas de invocarlo, las dos equivalentes:

* como `--pre-upgrade-scripts` de un `-u` (entra por `migrate(cr, version)`);
* como script suelto contra la base restaurada: `python3 prepare_post_odu.py <db>`.
  Es la forma que usa el step de runbot, porque los `--pre-upgrade-scripts` solo
  corren cuando el comando lleva `-u` (`odoo/modules/loading.py`) y este trabajo no
  necesita el hook, necesita el momento: despues del restore, antes del `-u all`.

Solo SQL y stdlib: la base esta mixta (core nuevo / modulos viejos), no hay registry, y
corriendo suelto dentro del container el paquete `odoo` puede no ser importable.

NO va en `pre_upgrade_scripts/`: esa carpeta corre en los pases de clientes reales, y
esto es exclusivamente para nuestro circuito de tests.
"""

import glob
import importlib.util
import json
import logging
import os

_logger = logging.getLogger(__name__)

# Mismo nombre de tabla y misma DDL que `odoo.upgrade.testing.UpgradeCommon._init_db`.
DATA_TABLE = "upgrade_test_data"

# La columna `class` del framework guarda el nombre de la clase base del test. Hoy nadie la
# lee (es informativa), pero la llenamos bien igual. Por default un UpgradeCase; la
# declaracion marca sus IntegrityCase en `INTEGRITY_CASES`.
DEFAULT_CLASS = "UpgradeCase"
INTEGRITY_CLASS = "IntegrityCase"

DECLARATION_FILENAME = "prepare_post_odu.py"


def _declarations(root):
    """Devuelve [(modulo, path)] de cada `<modulo>/tests/prepare_post_odu.py` bajo `root`."""
    pattern = os.path.join(root, "*", "tests", DECLARATION_FILENAME)
    for path in sorted(glob.glob(pattern)):
        module = os.path.basename(os.path.dirname(os.path.dirname(path)))
        yield module, path


def _load(module, path):
    """Carga la declaracion por path, sin registrarla en `sys.modules`."""
    spec = importlib.util.spec_from_file_location(
        f"odoo.upgrade.testing_post_odu.{module}", path
    )
    declaration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(declaration)
    return declaration


def _table_exists(cr, table):
    """Mismo check que hace `UpgradeCommon._init_db` del framework."""
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s", (table,))
    return bool(cr.rowcount)


def _init_table(cr):
    if _table_exists(cr, DATA_TABLE):
        return
    _logger.info("Creating table %s", DATA_TABLE)
    cr.execute(
        """
        CREATE TABLE upgrade_test_data (
            key VARCHAR(255) PRIMARY KEY,
            class varchar,
            value JSONB NOT NULL
        )
        """
    )


def migrate(cr, version):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    declarations = list(_declarations(root))
    if not declarations:
        _logger.info("prepare_post_odu: no hay declaraciones bajo %s", root)
        return

    _init_table(cr)

    written = []
    existing = []
    for module, path in declarations:
        declaration = _load(module, path)
        if not hasattr(declaration, "prepare"):
            # Explicito y ruidoso: una declaracion muda deja el check en falso verde, que
            # es exactamente lo que este runner viene a cerrar.
            raise AttributeError(f"{path} debe exponer una funcion `prepare(cr)`")

        # Un error aca tampoco se traga: preferimos volar el upgrade de la base de tests
        # antes que dejar checks skipeados en silencio.
        values = declaration.prepare(cr) or {}
        integrity_cases = set(getattr(declaration, "INTEGRITY_CASES", ()))

        for suffix, value in values.items():
            key = f"{module}.tests.{suffix}"
            data_class = INTEGRITY_CLASS if suffix in integrity_cases else DEFAULT_CLASS
            cr.execute(
                """
                INSERT INTO upgrade_test_data (key, class, value)
                     VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (key) DO NOTHING
                """,
                (key, data_class, json.dumps(value, sort_keys=True)),
            )
            # Si la key ya estaba (el `test_prepare` oficial corrio pre-ODU), la respetamos:
            # su valor lo escribio quien si pudo ver la base vieja.
            (written if cr.rowcount else existing).append(key)

    for key in written:
        _logger.info("prepare_post_odu: sembrada la key %s", key)
    for key in existing:
        _logger.info("prepare_post_odu: la key %s ya existia, no se toca", key)
    _logger.info(
        "prepare_post_odu: %s keys sembradas, %s ya existentes, %s declaraciones",
        len(written),
        len(existing),
        len(declarations),
    )


if __name__ == "__main__":
    import sys

    import psycopg2

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) != 2:
        raise SystemExit("uso: prepare_post_odu.py <db_name>")

    connection = psycopg2.connect(dbname=sys.argv[1])
    try:
        with connection.cursor() as cursor:
            migrate(cursor, None)
        connection.commit()
    finally:
        connection.close()
