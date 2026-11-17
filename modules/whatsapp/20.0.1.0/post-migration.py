import logging

from odoo.exceptions import UserError
from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)

# La escribe scripts/pre_odoo/190_200/030-backup_whatsapp_template_phone_field.py, del
# otro lado del pase.
BACKUP_TABLE = "whatsapp_template_phone_field_bu"


def migrate(cr, version):
    """Las plantillas de WhatsApp que vienen de 19 siguen mandando a su phone_field.

    Odoo 20 suma `whatsapp.template.use_default_recipient`, que nace en True: con True
    el envío (masivo o a un registro) toma el destinatario por defecto del registro e
    ignora `phone_field`. En 19 siempre mandaba a `phone_field`, así que una plantilla
    que le escribía al vendedor o a otro contacto pasaría a escribirle al cliente sin
    aviso.

    Por eso cada plantilla que viene de 19 queda con `use_default_recipient = False` y
    con el `phone_field` que tenía antes del pase. Las que se creen en 20 toman lo que
    trae Odoo. Si un campo de teléfono de 19 ya no existe en 20, esa plantilla queda
    con el destinatario por defecto y se avisa.

    Se escribe por SQL: así no corren los compute ni el seguimiento del chatter. El
    campo se valida antes con el mismo método que usa Odoo.
    """
    _logger.info("Running post-migration for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        # Sin respaldo no se sabe qué phone_field tenía cada plantilla en 19. Se
        # conservan las que todavía lo tienen; si el pase lo vació, quedan con el
        # destinatario por defecto.
        _logger.warning(
            "%s does not exist: did the pre-odoo script run? Only templates that still have a phone_field are kept",
            BACKUP_TABLE,
        )
        cr.execute(
            SQL(
                """
                UPDATE whatsapp_template
                   SET use_default_recipient = FALSE
                 WHERE phone_field IS NOT NULL
                   AND use_default_recipient
                """
            )
        )
        _logger.info("%s templates keep their phone_field", cr.rowcount)
        return

    cr.execute(
        SQL(
            """
            SELECT t.id, t.name, t.model, bu.phone_field
              FROM %s bu
              JOIN whatsapp_template t ON t.id = bu.id
             ORDER BY t.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    env = util.env(cr)
    valid_ids, invalid = [], []
    for template_id, name, model, phone_field in cr.fetchall():
        try:
            env[model]._find_value_from_field_path(phone_field)
        except (KeyError, UserError):
            invalid.append((name, model, phone_field))
            continue
        valid_ids.append(template_id)

    if valid_ids:
        cr.execute(
            SQL(
                """
                UPDATE whatsapp_template t
                   SET use_default_recipient = FALSE,
                       phone_field = bu.phone_field
                  FROM %s bu
                 WHERE t.id = bu.id
                   AND t.id = ANY(%s)
                """,
                SQL.identifier(BACKUP_TABLE),
                valid_ids,
            )
        )
    _logger.info("%s templates keep their 19.0 phone_field", len(valid_ids))

    if invalid:
        log_message(
            cr,
            "WhatsApp templates whose 19.0 phone field does not exist in 20.0. They now send "
            "to the default recipient of the record: check their phone field before using "
            "them: " + "; ".join("%s (%s, %s)" % row for row in invalid),
            "warning",
            module="whatsapp",
        )
