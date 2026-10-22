# Test declarativo de la migración 19->20 de website_sale_cart_offcanvas.
#
# En 19 el panel lateral del carrito se prendía por sitio, eligiendo "Open cart panel" en
# el ajuste `website.add_to_cart_action`, y de fábrica venía apagado ('stay'). Odoo 20
# eliminó ese ajuste del core, así que el módulo pasa a tener el suyo,
# `website.cart_offcanvas_enabled`.
#
# La tarea 76823 pide que en 20 la opción quede activada para todos los clientes, y que al
# que no la tenía se le avise por customer note. Por eso el campo nace con `default=True`:
# al crear la columna, el -u la llena con ese valor en los sitios que ya existen.
#
# Lo que este check fija es justamente eso, que es el cambio de comportamiento pedido y lo
# único que se puede leer de un registro después del -u:
#
#   el sitio queda con el panel activado, venga de donde venga su valor de 19
#
# Las dos ramas de origen ('open_offcanvas' y cualquier otro valor) terminan en el mismo
# estado a propósito: lo que las distingue no es un campo del sitio sino el customer note
# que emite modules/website_sale_cart_offcanvas/20.0.1.0.0/post-migration.py, que no se
# declara acá. Por eso alcanza con el sitio por defecto y no hace falta siembra.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que recibimos se
# da por buena.
#
# Supuesto a confirmar en runbot: el ancla es `base.default_website`, que es donde Odoo 20
# declara el sitio por defecto (odoo/addons/base/data/website.xml); en 19 el registro era
# `website.default_website`. Si el pase no reapunta el xmlid, el check va a fallar por ref
# ausente y el ancla pasa a ser el id viejo.

EXPECTED = {
    "website": {
        # El sitio por defecto existe en cualquier base con website instalado, así que
        # ancla sin siembra. Después del -u tiene que tener el panel activado: es el
        # cambio que pidió la tarea, y el que dispara el aviso al cliente que no lo tenía.
        ref("base.default_website"): {
            "cart_offcanvas_enabled": True,
        },
    },
}
