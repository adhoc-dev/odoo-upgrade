import logging

_logger = logging.getLogger(__name__)

# Casos de base_dynamic_message/20.0.1.0.0/pre-migration.py, que en el salto a 20
# pasa a la forma de 20 los operadores de dominio que 19 aceptaba y 20 rechaza.
# Los verifica base_dynamic_message/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: el modulo no trae data de prueba, asi que no hay
# ninguna linea de mensaje dinamico con xmlid en la base canonica.
#
# El mensaje no se confirma: confirmar crea un campo manual y una vista sobre
# res.partner, y eso le cambiaria el formulario de contactos a todos los demas
# tests de la base. El check mira el dominio y el codigo de cada linea; el
# compute del campo lo cubre el test de modules/base_dynamic_message/tests/.

MESSAGE = "dynamic_message_operators"
LINES = [
    # (xmlid, dominio en 19, mensaje)
    ("dynamic_message_line_ne", '[("email", "<>", False)]', "<p>Tiene email</p>"),
    ("dynamic_message_line_eq", '[("name", "==", "Azure Interior")]', "<p>Es Azure</p>"),
    ("dynamic_message_line_upper", '[("name", "ILIKE", "azure")]', "<p>Parece Azure</p>"),
    # preservacion: un dominio valido, con un valor que se escribe como un operador
    ("dynamic_message_line_valid", '[("ref", "in", ["A", "IN"])]', "<p>Referencia A o IN</p>"),
]


def migrate(env):
    if "ir.model.dynamic_message" not in env:
        _logger.info("base_dynamic_message is not installed - not seeding it")
        return
    env["ir.model.dynamic_message"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.%s" % MESSAGE,
                "values": {
                    "name": "Operadores de dominio (siembra de upgrade)",
                    "model_id": env["ir.model"]._get("res.partner").id,
                    # required compute fields: the form fills them by onchange, the ORM does not
                    "view_to_inherit_id": env.ref("base.view_partner_form").id,
                    "depends": "email,name,ref",
                    "alert_type": "info",
                },
                "noupdate": True,
            }
        ]
    )
    message = env.ref("upgrade_prepare_demo.%s" % MESSAGE)
    env["ir.model.dynamic_message.line"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.%s" % xmlid,
                "values": {"dynamic_message_id": message.id, "domain": domain, "message": text},
                "noupdate": True,
            }
            for xmlid, domain, text in LINES
        ]
    )
