import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/190_200/020-backup_aeroo_report_file.py, antes del pase.
BACKUP_TABLE = "ir_act_report_xml_report_file_bu"


def migrate(cr, version):
    """Repone la ruta de la plantilla que el pase se llevó con el campo del core.

    Solo donde quedó vacía: lo que el -u ya cargó —un dato sin noupdate, como el reporte de
    account_debt_report— le gana al respaldo.
    """
    _logger.info("Running post-migration of report_aeroo for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        # No es "no había rutas que reponer": es que nadie las guardó.
        _logger.warning("No existe %s: no se repuso ninguna ruta. ¿Corrió el pre-odoo?", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            UPDATE ir_act_report_xml r
               SET report_file = b.report_file
              FROM %s b
             WHERE r.id = b.id
               AND (r.report_file IS NULL OR r.report_file = '')
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    _logger.info("Restored %s Aeroo template paths from %s", cr.rowcount, BACKUP_TABLE)
