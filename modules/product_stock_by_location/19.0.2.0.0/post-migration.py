import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill de `show_stock_on_products` al invertir el default a True (tarea #70789).

    Desde 19.0.2.0.0 el campo `stock.location.show_stock_on_products` viene
    prendido por defecto (opt-out): el detalle de stock por ubicacion se muestra
    salvo que se apague explicitamente. El nuevo default solo aplica a ubicaciones
    nuevas; las existentes conservan su valor almacenado. Para que una base que
    viene de 17/18 (donde el flag era ignorado por el widget de venta y estaba en
    False "sin configurar") siga viendo lo mismo que antes, prendemos el flag en
    todas las ubicaciones internas existentes.

    Guarda por version de origen: solo backfillea si la base viene de < 19
    (17/18 -> 19). Si ya estaba en 19 (p. ej. un pase futuro 19 -> 20 sobre una
    base que no actualizo el modulo antes del pase), NO toca nada: ahi un False
    puede ser una decision deliberada del cliente que no debe pisarse (#70789).
    Esto refuerza que odoo-upgrade solo corre durante el pase de version.
    """
    if version and version.split(".")[0].isdigit() and int(version.split(".")[0]) >= 19:
        _logger.info(
            "product_stock_by_location: base ya en 19 (version=%s); se omite el backfill",
            version,
        )
        return

    cr.execute(
        """
        UPDATE stock_location
           SET show_stock_on_products = TRUE
         WHERE usage = 'internal'
           AND show_stock_on_products IS NOT TRUE
        """
    )
    _logger.info(
        "product_stock_by_location: show_stock_on_products=True en %d ubicaciones internas (version origen=%s)",
        cr.rowcount,
        version,
    )
