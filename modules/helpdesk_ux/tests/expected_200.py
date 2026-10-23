# Test declarativo de helpdesk_ux/20.0.1.0.0/pre-migration.py.
#
# La transformacion: el interruptor "No enviar correo de etapa" se apaga en
# todos los tickets al pasar a 20.
#
#   ticket con el interruptor prendido  -> apagado
#   ticket con el interruptor apagado   -> apagado (preservacion)
#
# El ticket prendido lo siembra tests/pre_odu/helpdesk_ux/190_200/
# 010-dont_send_stage_email_on.py: la demo del modulo no trae ninguno.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "helpdesk.ticket": {
        # Rama prendido -> apagado: la siembra lo deja en True. Si sigue en
        # True, el script no corrio y el ticket se va a comer el proximo
        # correo de etapa despues del pase.
        ref("upgrade_prepare_demo.helpdesk_ticket_dont_send_stage_email_on"): {
            "dont_send_stage_email": False,
        },
        # Preservacion: un ticket de la demo del modulo, con el interruptor
        # apagado. Si queda en True, el script prendio lo que tenia que apagar.
        ref("helpdesk_ux.helpdesk_ticket_1"): {
            "dont_send_stage_email": False,
        },
    },
}
