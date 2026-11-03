import logging

_logger = logging.getLogger(__name__)

# Caso de modules/sale_order_type_invoice_policy/tests/expected_200.py: que el valor de
# services_delivered sobreviva al pase, en una base que llega con el xmlid del campo
# apuntando al modulo padre. No lo migra ningun script.
#
# POR QUE HAY QUE SEMBRAR: la base canonica esta en el ultimo 19, donde el traspaso del
# xmlid al bridge ya lo hizo migrations/19.0.1.2.0 del modulo, asi que el caso no existe en
# ella. La siembra lo devuelve al estado de una base que se quedo en un 19 anterior al
# 28/09/2026. Es el estado real de un cliente que no paso por 19.0.1.2.0, no una combinacion
# inventada: el campo vivio en el modulo padre desde el 13/05/2026.
#
# Lo que el check cuida: si Odoo dejara de auto-instalar el bridge en el -u, o tratara el
# campo como huerfano antes de cargarlo, le borraria la columna y el tipo de venta perderia
# la opcion marcada, sin error y sin aviso.

MODULE = "sale_order_type_invoice_policy"
BRIDGE = "sale_order_type_invoice_policy_project"
XMLID_NAME = "field_sale_order_type__services_delivered"
MARCADO = "upgrade_prepare_demo.sot_services_delivered_on"
SIN_MARCAR = "upgrade_prepare_demo.sot_services_delivered_off"


def migrate(env):
    if "sale.order.type" not in env or "services_delivered" not in env["sale.order.type"]._fields:
        # Sin el bridge instalado no hay campo que sembrar: lo dice el check como ref ausente
        _logger.info("%s is not in this database - not seeding it", BRIDGE)
        return

    env["sale.order.type"]._load_records(
        [
            {
                "xml_id": MARCADO,
                "values": {
                    "name": "Delivered, excluding prepaid services",
                    "invoice_policy": "delivery",
                    "services_delivered": True,
                },
                "noupdate": True,
            },
            {
                "xml_id": SIN_MARCAR,
                "values": {
                    "name": "Delivered quantities",
                    "invoice_policy": "delivery",
                    "services_delivered": False,
                },
                "noupdate": True,
            },
        ]
    )

    # El traspaso al reves: asi llega una base que no corrio 19.0.1.2.0. Idempotente, y con
    # la guarda de unicidad de (module, name) por si el padre ya tiene la fila.
    env.cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s
         WHERE module = %s
           AND model = 'ir.model.fields'
           AND name = %s
           AND NOT EXISTS (
               SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s
           )
        """,
        (MODULE, BRIDGE, XMLID_NAME, MODULE, XMLID_NAME),
    )
    _logger.info("%s.%s moved back to %s to reproduce a pre-19.0.1.2.0 database", BRIDGE, XMLID_NAME, MODULE)
