import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# La lee modules/l10n_ar_edi_ux/20.0.1.0.0/post-migration.py, del otro lado del pase.
BACKUP_TABLE = "res_partner_arca_activity_bu"
TARGET_VERSION = 20


def migrate(cr, version):
    """Respalda las actividades ARCA de cada contacto antes del pase.

    l10n_ar_edi_ux guarda las actividades del padrón en el m2m
    res_partner_arca_activity_rel, que apunta a l10n_ar.arca.activity. En 19 ese modelo lo
    trae l10n_ar_reports_simple; en 20 vive en l10n_ar, con los mismos códigos y otro módulo
    en el xmlid. Si el pase borra los registros viejos en vez de reasignarlos, el m2m se vacía
    en cascada del lado de Odoo, antes de que corra cualquier script nuestro.

    Se respalda el código, no el id: es único en las dos versiones y es lo que permite volver
    a encontrar la actividad del otro lado.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    # El gate de módulo va acá porque el pre-odoo corre sobre toda la base, sin filtrar.
    if not should_back_up(
        cr, BACKUP_TABLE, first_target=TARGET_VERSION, last_target=TARGET_VERSION, modules=["l10n_ar_edi_ux"]
    ):
        return

    _logger.info("Respaldando las actividades ARCA de los contactos en %s", BACKUP_TABLE)
    backed_up = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT DISTINCT r.partner_id, a.code
          FROM res_partner_arca_activity_rel r
          JOIN l10n_ar_arca_activity a ON a.id = r.arca_activity_id
        """,
        primary_key=("partner_id", "code"),
    )
    _logger.info("Se respaldaron %s actividades de contactos", backed_up)
