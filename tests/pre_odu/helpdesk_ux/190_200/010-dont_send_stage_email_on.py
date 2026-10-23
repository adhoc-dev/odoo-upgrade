import logging

_logger = logging.getLogger(__name__)

# Caso de helpdesk_ux/20.0.1.0.0/pre-migration.py, que al pasar a 20 apaga el
# interruptor "No enviar correo de etapa" en todos los tickets. Lo verifica
# helpdesk_ux/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la demo de helpdesk_ux trae tickets, pero todos con
# el interruptor apagado. La rama que el script cambia es un ticket con el
# interruptor prendido, y esa no la trae ninguna data de prueba.
#
# El interruptor se prende recien despues de que corre el tracking del alta:
# el modulo lo apaga en el commit cuando la etapa cambia, y el alta cuenta como
# cambio de etapa. Prendido en el mismo create, el ticket llegaria apagado al
# pase y el check daria verde sin que el script haga nada.

TICKET_XMLID = "upgrade_prepare_demo.helpdesk_ticket_dont_send_stage_email_on"


def migrate(env):
    if (
        "helpdesk.ticket" not in env
        or "dont_send_stage_email" not in env["helpdesk.ticket"]._fields
    ):
        _logger.info("helpdesk_ux is not installed - not seeding it")
        return
    team = env.ref("helpdesk.helpdesk_team1", raise_if_not_found=False)
    if not team:
        # Sin el equipo de la demo no hay caso: lo dice el check como ref ausente
        _logger.info("helpdesk.helpdesk_team1 is not in this database - not seeding it")
        return
    env["helpdesk.ticket"]._load_records(
        [
            {
                "xml_id": TICKET_XMLID,
                "values": {
                    "name": "Ticket with the stage email toggle on",
                    "team_id": team.id,
                },
                "noupdate": True,
            }
        ]
    )
    env.flush_all()
    env.cr.precommit.run()
    ticket = env.ref(TICKET_XMLID)
    ticket.dont_send_stage_email = True
    env.flush_all()
