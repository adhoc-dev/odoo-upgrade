# sale_order_type_invoice_policy 19 -> 20 (tarea 76458).
#
# services_delivered vivio en este modulo entre el 13/05 y el 28/09 de 2026, cuando paso al
# bridge sale_order_type_invoice_policy_project (depende de sale_project). El traspaso del
# xmlid lo hacia migrations/19.0.1.2.0/pre-migration.py del propio modulo, y al migrar el
# modulo a 20 esa carpeta se borra (ADR 0050 de actua-20): una base que salta a 20 desde un
# 19 anterior nunca lo corre y llega con el xmlid apuntando al modulo padre, que en 20 ya no
# declara el campo.
#
# NO MIGRA NINGUN SCRIPT: es el check de que el dato no se pierde. Probado el 03/11/2026
# sobre una base 20 que reproduce ese estado: el bridge se auto-instala en el -u, el campo
# sigue en el registry y Odoo no lo trata como huerfano, asi que el valor sobrevive. El
# comentario del pre-migration de 19.0.1.2.0 dice lo contrario ("auto_install does not cover
# this"); el codigo de 20 lo desmiente. Si esa conducta cambia, este check se pone en rojo
# antes de que un cliente pierda la opcion.
#
# El estado de partida lo siembra tests/pre_odu/sale_order_type_invoice_policy/190_200/
# 010-services_delivered_xmlid_on_parent.py: la base canonica llega con el traspaso ya hecho,
# asi que la siembra lo devuelve al estado de una base que se quedo en un 19 anterior.
EXPECTED = {
    "sale.order.type": {
        # Preservacion del dato: parte de services_delivered = True con el xmlid del campo
        # apuntando al modulo padre. Si queda en False, el campo quedo huerfano al cargar el
        # padre, Odoo le borro la columna y el bridge lo recreo vacio: el tipo de venta deja
        # de excluir los servicios prepagos y los factura por cantidad entregada. Si el campo
        # directamente no existe, el bridge no se auto-instalo en el -u.
        ref("upgrade_prepare_demo.sot_services_delivered_on"): {
            "services_delivered": True,
        },
        # El mismo tipo de venta sin la opcion marcada, con el xmlid igual de mudado. Tiene
        # que seguir en False: separa "el dato sobrevivio" de "la columna quedo toda en True".
        ref("upgrade_prepare_demo.sot_services_delivered_off"): {
            "services_delivered": False,
        },
    },
}
