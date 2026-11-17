# Test declarativo de la migración 19->20 de whatsapp.
#
# En 19 una plantilla de WhatsApp manda siempre al teléfono de su `phone_field`. Odoo 20
# suma `use_default_recipient`, que nace en True: con True el envío ignora `phone_field`
# y manda al destinatario por defecto del registro. La tarea 76806 decidió conservar lo de
# 19 en las plantillas que vienen de 19:
#
#   plantilla de 19 con un phone_field válido en 20 -> use_default_recipient = False,
#                                                       phone_field = el de 19
#   plantilla de 19 con un phone_field que no existe en 20 -> sin cambios, y se avisa
#
# El phone_field de 19 lo respalda scripts/pre_odoo/190_200/030-backup_whatsapp_template_phone_field.py
# y lo repone modules/whatsapp/20.0.1.0/post-migration.py.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que recibimos se
# da por buena.
#
# La rama del campo que no existe en 20 no tiene ancla: en 19 la validación de la
# plantilla no deja guardar un campo inexistente, así que haría falta sembrar uno que la
# 20 saque. Queda cubierta por el aviso del script, no por este check.

EXPECTED = {
    "whatsapp.template": {
        # Plantilla de 19 con un phone_field propio: la de data de whatsapp, que en 19
        # manda a `whatsapp_number` y en 20 viene sin phone_field. Si queda con
        # use_default_recipient en True, o con phone_field vacío, el pase la dejó
        # mandando al destinatario por defecto y el script no la repuso.
        ref("whatsapp.whatsapp_template_discuss_channel_reviver"): {
            "use_default_recipient": False,
            "phone_field": "whatsapp_number",
        },
    },
}
