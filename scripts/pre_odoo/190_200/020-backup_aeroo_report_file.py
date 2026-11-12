import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/report_aeroo/20.0.1.0.0/post-migration.py, del otro lado del pase.
BACKUP_TABLE = "ir_act_report_xml_report_file_bu"
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20


def migrate(cr, version):
    """Guarda la ruta de la plantilla de los reportes Aeroo antes de mandar la base a Odoo.

    En 20.0 Odoo saca report_file de ir.actions.report (commit 80e1a4464f7) y su script de
    pase borra la columna. report_aeroo vuelve a declarar el campo, así que el -u lo recrea
    vacío y la ruta no vuelve sola: los reportes que vienen de un dato con noupdate="1"
    (picking_waybill, stock_picking_labels, el de ejemplo del propio módulo) no los repone
    el -u, y los que creó el cliente a mano, tampoco. Al imprimir cortan con
    "No Aeroo Reports template filename provided".

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base vieja,
    con el Odoo de la versión de origen.
    """
    if not should_back_up(
        cr, BACKUP_TABLE, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=["report_aeroo"]
    ):
        return

    # Todos los aeroo con ruta, no solo los de tml_source = 'file': el origen de la
    # plantilla se cambia desde la interfaz y la ruta vieja sigue sirviendo.
    rows = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, report_file
          FROM ir_act_report_xml
         WHERE report_type = 'aeroo'
           AND report_file IS NOT NULL
           AND report_file != ''
        """,
    )
    _logger.info("Backing up %s Aeroo template paths into %s", rows, BACKUP_TABLE)
