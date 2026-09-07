import logging

# El job corre como python pelado, pero `odoo.tools` importa bien: lo confirmó la sonda 900 de la
# task 72527 en la corrida del 28/08.
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Script que falla A PROPÓSITO, para probar en vivo la task 73363: que el job conserve el log
# completo de la corrida y que un fallo genere el error log de la etapa Pre-ODU.
#
# Hereda del 910 de la task 72527, que ya probó lo anterior — que el error se propaga, que el
# step no crea el job de submit y que la base no se dumpea. Eso se sigue verificando acá, porque
# el cambio de la 73363 no debe haberlo roto.
#
# Evidencia esperada:
#   * el job `pre-odoo` termina en error y NO se crea el job de submit,
#   * la request queda en `validated`, con `task_state` en odooupgrade_run_pre_odoo_scripts,
#   * la request tiene el adjunto "Pre Odoo Log" con el log COMPLETO de la corrida, no un extracto,
#   * se creó UN error log con la etapa `pre-odoo/910-fail_on_purpose.py`, la request quedó con
#     `with_error_log` y `error_category` = "Error en scripts",
#   * un solo mensaje de error en el chatter, no dos.
#
# El error log va a quedar SIN módulo asociado, y está bien: el módulo se deriva del nombre del
# script y `fail_on_purpose` no es uno. Un script real (`010-stock_account_ux.py`) sí lo resuelve.
#
# BORRAR después de la prueba: NO puede quedar en una imagen. Nunca mergear a master.

# Solo falla en la base de prueba, para que si este archivo se escapa a un build por error no
# rompa un pase de cliente. El identificador es `db_host`, NO el nombre de la base: la base
# PostgreSQL se llama `odoo` en todas (verificado en la corrida del 28/08, donde el guard por
# `current_database()` nunca disparó). `db_host` trae `old-<cliente>-<dd-mm>-<n>-pg-rw`, así que
# el substring del cliente alcanza y aguanta el prefijo `2old-` del namespace.
TARGET_HOST = "dp-latam"


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
        "Falla deliberada del pre_odoo_script 910 (task 73363) sobre %s. "
        "No es un error real: verifica que la corrida se detenga, que el log completo vuelva al "
        "provider y que se cree el error log de la etapa Pre-ODU. "
        "Si aparece en un pase que no es la prueba, sacar este script del build." % host
    )
