import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Completa la cuenta de las líneas de pago "Batch Deposit" sin cuenta.

    account_batch_payment agrega el método "Batch Deposit" (mode='multi') y, al
    instalarse sobre una base con diarios bancarios ya existentes, Odoo crea las
    account.payment.method.line en esos diarios SIN payment_account_id
    (account ::_auto_link_payment_methods). Esas líneas nunca pasaron por el
    create() de account.journal de saas_client_account, así que quedan sin cuenta
    y no generan asiento -> dispara el control de "métodos de pago sin cuenta" en
    la validación post-migración.

    Les asignamos la misma cuenta que usa el método manual del diario. Idempotente:
    solo toca líneas con payment_account_id NULL.
    """
    _logger.info("Running post-migration for version %s", version)

    cr.execute(
        SQL(
            """
            UPDATE account_payment_method_line line
               SET payment_account_id = manual_line.payment_account_id
              FROM account_journal journal,
                   account_payment_method method,
                   account_payment_method_line manual_line
             WHERE line.journal_id = journal.id
               AND line.payment_method_id = method.id
               AND line.payment_account_id IS NULL
               AND method.code = %(batch_code)s
               AND manual_line.journal_id = journal.id
               AND manual_line.code = %(manual_code)s
               AND manual_line.payment_account_id IS NOT NULL
            """,
            batch_code="batch_payment",
            manual_code="manual",
        )
    )
    _logger.info(
        "Backfilled %s batch deposit payment method lines with the manual method account",
        cr.rowcount,
    )
