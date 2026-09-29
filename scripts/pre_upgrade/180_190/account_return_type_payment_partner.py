import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Crea la columna account_return_type.payment_partner_id antes del upgrade.

    En Odoo estandar (account_reports) payment_partner_id es un campo related
    NO almacenado (related='payment_partner_bank_id.partner_id'), por lo que no
    tiene columna fisica. En l10n_ar_account_reports lo pisamos como stored sin
    related ni compute:

        payment_partner_id = fields.Many2one(store=True, related=False)

    El paso de upgrade "Recargamos traducciones de todos los idiomas instalados"
    corre con el registry nuevo (donde el campo ya es stored y entra en los
    SELECT) ANTES de que _auto_init cree la columna, y explota con:

        psycopg2.errors.UndefinedColumn:
        column account_return_type.payment_partner_id does not exist

    Creamos la columna aca (fase pre-upgrade, antes del -u) y la poblamos con el
    valor que tenia el related original (partner de la cuenta bancaria de pago).
    Si la tabla todavia no existe, el -u la crea de cero ya con la columna, asi
    que no hay nada que hacer.

    Ticket #122782.
    """
    _logger.info("Running pre-upgrade script 'account_return_type_payment_partner' for version %s", version)

    if not util.table_exists(cr, "account_return_type"):
        return

    if util.column_exists(cr, "account_return_type", "payment_partner_id"):
        return

    util.create_column(cr, "account_return_type", "payment_partner_id", "int4")
    cr.execute(
        """
        UPDATE account_return_type art
           SET payment_partner_id = rpb.partner_id
          FROM res_partner_bank rpb
         WHERE art.payment_partner_bank_id = rpb.id
        """
    )
