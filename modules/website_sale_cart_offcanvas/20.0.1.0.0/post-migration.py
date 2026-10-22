import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import add_customer_note

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/190_200/020-website_sale_cart_offcanvas_backup.py, del otro
# lado del pase.
BACKUP_TABLE = "website_add_to_cart_action_bu"
# El valor con el que el módulo se activaba en 19.
ENABLED_IN_19 = "open_offcanvas"


def migrate(cr, version):
    """Avisa a qué sitios se les activó solo el panel lateral del carrito.

    En 19 el panel se prendía eligiendo "Open cart panel" en el ajuste
    `add_to_cart_action` del sitio, y de fábrica venía apagado. Odoo 20 eliminó ese
    ajuste, así que el módulo pasa a tener el suyo, `cart_offcanvas_enabled`, que nace
    activado: después del pase el panel queda prendido en todos los sitios.

    Ese cambio de comportamiento es el pedido de la tarea 76823, y no hay nada que
    escribir acá: el default del campo ya lo aplica a los sitios que existen. Lo que sí
    sale de este script es el dato del customer note, que solo tiene sentido para el
    cliente que NO lo tenía activado: a ese se le prendió algo que no había pedido.
    """
    _logger.info("Running post-migration for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        # No es "no había sitios": es que nadie miró. Emitir una lista vacía acá le diría
        # al cliente que no le cambió nada, sin que nadie lo haya verificado.
        _logger.warning(
            "%s does not exist: nothing reported. Did the pre-odoo script run?",
            BACKUP_TABLE,
        )
        return

    cr.execute(
        SQL(
            "SELECT name, add_to_cart_action FROM %s WHERE add_to_cart_action IS DISTINCT FROM %s ORDER BY id",
            SQL.identifier(BACKUP_TABLE),
            ENABLED_IN_19,
        )
    )
    # `website.name` es un Char en 19 (no es traducible), así que la columna
    # respaldada trae el nombre tal cual. La clave `sitio` es la que lee el mensaje
    # de la nota: si cambia acá, cambia allá.
    sitios = [{"sitio": nombre} for nombre, _accion in cr.fetchall()]

    # Sin sitios también se emite: la tabla estaba, así que "no le cambió nada" es un
    # resultado y el mensaje puede querer decirlo.
    add_customer_note(
        cr,
        {
            "cart_offcanvas_sitios_activados": sitios,
            "cart_offcanvas_sitios_activados_total": len(sitios),
        },
    )
    _logger.info("%s sites got the cart side panel on without asking for it", len(sitios))
