import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/whatsapp/20.0.1.0/post-migration.py, del otro lado del pase.
#
# En 19 cada plantilla de WhatsApp manda al teléfono de su `phone_field`, que es
# obligatorio. Odoo 20 suma `use_default_recipient`, que nace en True: con True el envío
# ignora `phone_field` y manda al destinatario por defecto del registro, y
# `_compute_phone_field` lo vacía. Si el pase lo recalcula, el campo que tenía cada
# plantilla no se puede leer del otro lado. Por eso se respalda acá, antes de mandar la
# base.
BACKUP_TABLE = "whatsapp_template_phone_field_bu"
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Respalda el phone_field de cada plantilla de WhatsApp antes del pase a Odoo.

    Solo respalda: no cambia nada de la base vieja.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    # Borra BACKUP_TABLE antes de cualquier condición: una tabla de una corrida anterior
    # no puede viajar en un request al que el script no aplica. La plataforma no filtra
    # por módulo: el módulo se chequea acá.
    if not should_back_up(
        cr,
        BACKUP_TABLE,
        FIRST_TARGET_VERSION,
        FIRST_TARGET_VERSION,
        modules=["whatsapp"],
    ):
        return

    _logger.info("Backing up whatsapp.template.phone_field into %s", BACKUP_TABLE)
    rows = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, phone_field
          FROM whatsapp_template
         WHERE phone_field IS NOT NULL
        """,
    )
    _logger.info("%s rows backed up", rows)
