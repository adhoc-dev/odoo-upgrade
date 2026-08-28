import logging

# El job corre como python pelado, pero `odoo.tools` importa bien: lo confirmó la sonda 900 en la
# corrida del 28/08 sobre 2old-baratec-28-08-2.
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Script que falla A PROPÓSITO, para el punto 2 de la task 72527: confirmar que el runner del
# provider propaga el error, que el step no crea el job de submit y que la base NO se dumpea.
#
# El runner de runbot no propaga el exit code: un script podía fallar, la corrida seguía y la
# base se mandaba igual. Pasó dos veces y las dos el síntoma apareció doce minutos después
# disfrazado de otra cosa. Esto es la prueba de que el del provider no hace lo mismo.
#
# Prefijo 910 para correr después de la sonda 900: en una sola corrida se ve el entorno
# (el log no es transaccional, sobrevive al rollback) y después el corte.
#
# Evidencia esperada:
#   * el job `pre-odoo` termina en error y NO se crea el job de submit,
#   * la request queda en `validated`, con `task_state` en odooupgrade_run_pre_odoo_scripts,
#   * NINGUNA de las dos tablas de respaldo queda en la base — ni ir_ui_view_active_bu ni
#     stock_move_account_move_id_bu. Los cuatro scripts comparten un cursor y commitean al
#     salir, así que este raise tiene que arrastrarse todo. Eso prueba atomicidad además de
#     propagación.
#
# BORRAR después de la prueba: NO puede quedar en una imagen. Nunca mergear a master.

# Solo falla en la base de prueba, para que si este archivo se escapa a un build por error no
# rompa un pase de cliente. El identificador es `db_host`, NO el nombre de la base: la base
# PostgreSQL se llama `odoo` en todas (verificado en la corrida del 28/08, donde el guard por
# `current_database()` nunca disparó). `db_host` trae `old-<cliente>-<dd-mm>-<n>-pg-rw`, así que
# el substring del cliente alcanza y aguanta el prefijo `2old-` del namespace.
TARGET_HOST = "baratec"


def migrate(cr, version):
    """Levanta una excepción si corre sobre la base de prueba; en el resto no hace nada."""
    host = config.get("db_host") or ""

    if TARGET_HOST not in host:
        _logger.info(
            "sonda de falla inactiva (db_host=%r, solo falla si contiene %r); no se hace nada",
            host,
            TARGET_HOST,
        )
        return

    _logger.info("sonda de falla ACTIVA en %s: se corta la corrida a propósito", host)
    raise RuntimeError(
        "Falla deliberada del pre_odoo_script 910 (task 72527) sobre %s. "
        "No es un error real: verifica que la corrida se detenga y que la base no se dumpee. "
        "Si aparece en un pase que no es la prueba, sacar este script del build." % host
    )
