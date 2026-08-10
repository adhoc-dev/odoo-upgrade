import logging

_logger = logging.getLogger(__name__)

# La lee pre_upgrade_scripts/always/reactivate_views.py, del otro lado del upgrade.
BACKUP_TABLE = "ir_ui_view_active_bu"


def migrate(cr, version):
    """Guarda qué vistas están activas antes de mandar la base a Odoo.

    Odoo desactiva las vistas que le fallan durante su upgrade. Como nuestro `-u`
    suele arreglarlas, del otro lado las volvemos a activar, y para eso hace falta
    saber cuáles estaban activas acá.

    Sin `odoo.tools.SQL` ni `odoo.upgrade.util` a propósito: esto corre sobre la
    base vieja, con el Odoo de la versión de origen.
    """
    _logger.info("Backing up the active views into %s", BACKUP_TABLE)

    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    cr.execute("CREATE TABLE %s AS SELECT id FROM ir_ui_view WHERE active" % BACKUP_TABLE)
