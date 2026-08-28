import importlib
import logging
import os
import sys

_logger = logging.getLogger(__name__)

# Sonda TEMPORAL del punto 1 de la task 72527: documentar qué expone el entorno del job del
# provider a un pre_odoo_script. No cambia nada, solo loguea.
#
# El origen es el `ModuleNotFoundError: No module named 'odoo.modules'` que se comió el `060`
# en runbot: ahí `odoo` resuelve solo al namespace de upgrade-util, así que `import odoo` pasa
# y da falsa confianza. En el provider el job corre como `job_type "python"` (python pelado en
# el container de la base, sin `env` ni registry), y por eso el runner importa `odoo.sql_db`
# explícito. Lo que falta es la lista de lo que SÍ se puede asumir.
#
# Prefijo 900 para que corra al final y no altere el orden de los demás.
#
# BORRAR una vez que la salida quede documentada en el readme de pre_odoo_scripts.

# El import se intenta de verdad (no `find_spec`): lo que importa es si el módulo carga en este
# entorno, no si el archivo está en el path.
MODULES = [
    # Lo que ya sabemos que anda, para que quede en el mismo registro
    "odoo",
    "odoo.tools",
    "odoo.sql_db",
    # Lo que falló en runbot
    "odoo.modules",
    # ORM: no debería haber registry en un job python, confirmar qué carga igual
    "odoo.api",
    "odoo.fields",
    "odoo.models",
    "odoo.release",
    "odoo.addons",
    "odoo.service",
    # upgrade-util: es lo que usan los scripts del otro lado del pase
    "odoo.upgrade",
    "odoo.upgrade.util",
    "openupgradelib",
    "psycopg2",
    "requests",
]

# Solo claves de config sin secretos: nada de db_password ni admin_passwd. `db_host` va porque
# es lo único que identifica la base del pase: `db_name` es `odoo` en todas.
CONFIG_KEYS = ["addons_path", "data_dir", "server_wide_modules", "upgrade_path", "db_name", "db_host"]


def migrate(cr, version):
    """Loguea el entorno del job. Nunca levanta: comparte transacción con los demás scripts.

    Los 4 scripts del runner corren en un solo cursor y commitean al salir, así que una
    excepción acá tiraría abajo el respaldo de los otros. Por eso todo va envuelto.
    """
    try:
        _logger.info("=== sonda de entorno (task 72527) — version=%s ===", version)
        _logger.info("python: %s", sys.version.replace("\n", " "))
        _logger.info("executable: %s", sys.executable)
        _logger.info("cwd: %s", os.getcwd())

        for name in MODULES:
            try:
                module = importlib.import_module(name)
            except Exception as error:
                _logger.info("import %-22s NO  (%s: %s)", name, type(error).__name__, error)
                continue
            # __path__ solo en paquetes; en un namespace package dice de dónde sale cada pieza,
            # que es justo lo que distingue el Odoo completo del namespace de upgrade-util.
            where = getattr(module, "__file__", None) or list(getattr(module, "__path__", []) or [])
            _logger.info("import %-22s OK  (%s)", name, where)

        # `odoo.modules` como atributo: en runbot el import falla, pero conviene ver si el
        # atributo aparece igual por un import lateral de otro script.
        try:
            import odoo

            _logger.info("odoo.__path__: %s", list(getattr(odoo, "__path__", []) or []))
            _logger.info("odoo tiene atributo 'modules': %s", hasattr(odoo, "modules"))
        except Exception as error:
            _logger.info("no se pudo inspeccionar el paquete odoo: %s", error)

        try:
            from odoo.tools import config

            for key in CONFIG_KEYS:
                _logger.info("config[%s] = %s", key, config.get(key))
        except Exception as error:
            _logger.info("odoo.tools.config no disponible: %s", error)

        # Nombres de variables de entorno, SIN valores: MYSCRIPT_CALLBACK_PARAMS lleva el token
        # del provider y MYSCRIPT_* lo inyecta el job.
        env_keys = sorted(k for k in os.environ if k.startswith(("MYSCRIPT_", "ODOO", "PG")))
        _logger.info("variables de entorno relevantes (solo nombres): %s", env_keys)

        # Qué se puede hacer con el cursor que recibe migrate(): read-only.
        cr.execute("SELECT current_database(), current_user, version()")
        database, user, server = cr.fetchone()
        _logger.info("base: %s | usuario: %s | postgres: %s", database, user, server.split(",")[0])

        _logger.info("=== fin de la sonda ===")
    except Exception:
        # La sonda no puede ser el motivo de que un pase se caiga.
        _logger.exception("la sonda de entorno falló; se ignora para no abortar la corrida")
