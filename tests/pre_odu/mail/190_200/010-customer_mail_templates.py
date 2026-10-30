import json
import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-220-fix_mail_templates.py, que en los saltos a 20
# prueba el render de las plantillas de correo que cambio el cliente. Los
# verifica base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: el script mira solo las plantillas que cambio un
# usuario real, y ninguna data de prueba trae una. Las dos son del cliente, sin
# archivo de modulo, asi que el pase de Odoo no las toca.
#
# - una que no renderiza (lee un campo que no existe): el script la archiva;
# - una sana: el script la deja como esta.
#
# El body roto va por SQL: el write del ORM lo rechazaria. El write_uid tambien:
# todo lo que escribe este shell queda a nombre de OdooBot, y el script lo
# saltearia.

USER_XMLID = "upgrade_prepare_demo.user_mail_template_editor"
BROKEN_XMLID = "upgrade_prepare_demo.mail_template_customer_broken"
HEALTHY_XMLID = "upgrade_prepare_demo.mail_template_customer_healthy"
HEALTHY_BODY = '<p>Hola <t t-out="object.name"/></p>'
BROKEN_BODY = '<p>Hola <t t-out="object.campo_que_no_existe"/></p>'


def migrate(env):
    env["res.users"]._load_records(
        [
            {
                "xml_id": USER_XMLID,
                "values": {"name": "Mail template editor", "login": "mail_template_editor"},
                "noupdate": True,
            }
        ]
    )
    partner_model = env["ir.model"]._get_id("res.partner")
    env["mail.template"]._load_records(
        [
            {
                "xml_id": xmlid,
                "values": {"name": name, "model_id": partner_model, "body_html": HEALTHY_BODY},
                "noupdate": True,
            }
            for xmlid, name in (
                (BROKEN_XMLID, "Plantilla del cliente que no renderiza"),
                (HEALTHY_XMLID, "Plantilla del cliente sana"),
            )
        ]
    )
    env.flush_all()

    user_id = env.ref(USER_XMLID).id
    for xmlid, body in ((BROKEN_XMLID, BROKEN_BODY), (HEALTHY_XMLID, HEALTHY_BODY)):
        env.cr.execute(
            "UPDATE mail_template SET body_html = %s::jsonb, write_uid = %s WHERE id = %s",
            (json.dumps({"en_US": body}), user_id, env.ref(xmlid).id),
        )
    env.invalidate_all()
