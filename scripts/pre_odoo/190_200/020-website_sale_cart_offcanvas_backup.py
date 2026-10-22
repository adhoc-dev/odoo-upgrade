import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/website_sale_cart_offcanvas/20.0.1.0.0/post-migration.py, del otro lado
# del pase.
#
# website_sale_cart_offcanvas agregaba un tercer valor, 'open_offcanvas', a la selección
# website.add_to_cart_action de Odoo 19: con ese valor el carrito se abría en un panel
# lateral. Odoo 20 eliminó el ajuste entero y movió la decisión al botón del editor, así
# que el módulo pasa a tener un interruptor propio que nace activado para todos.
#
# Quién lo tenía activado en 19 no sobrevive al pase: Odoo borra la columna de un campo
# que su código ya no declara, y para cuando corre nuestro -u no queda nada que leer. Por
# eso se respalda acá, antes de mandar la base: del otro lado define a qué cliente se le
# avisa que la opción se le activó sola, que es justo el que NO la tenía.
BACKUP_TABLE = "website_add_to_cart_action_bu"
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Respalda el add_to_cart_action de cada sitio antes de que Odoo borre la columna.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    # Borra BACKUP_TABLE antes de cualquier condición: una tabla de una corrida anterior
    # no puede viajar en un request al que el script no aplica. La plataforma no filtra
    # por módulo: el módulo se chequea acá.
    if not should_back_up(
        cr,
        BACKUP_TABLE,
        FIRST_TARGET_VERSION,
        FIRST_TARGET_VERSION,
        modules=["website_sale_cart_offcanvas"],
    ):
        return

    # La columna puede no estar: el módulo se instaló pero el -u que agrega la selección
    # todavía no corrió. Sin ella no hay nada que respaldar, y el que lee avisa.
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        " WHERE table_name = 'website' AND column_name = 'add_to_cart_action'"
    )
    if not cr.fetchone():
        _logger.warning("website.add_to_cart_action does not exist: nothing backed up")
        return

    _logger.info("Backing up website.add_to_cart_action into %s", BACKUP_TABLE)
    rows = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, name, add_to_cart_action
          FROM website
        """,
    )
    _logger.info("%s rows backed up", rows)
