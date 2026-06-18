import logging

from odoo.tools import SQL

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

    Les asignamos la misma cuenta que usa el método manual del diario y, si el
    diario no tiene método manual con cuenta (ej. diarios de tarjeta de crédito),
    la cuenta por defecto del diario. Idempotente: solo toca líneas con
    payment_account_id NULL.
    """
    _logger.info("Running post-migration for version %s", version)

    cr.execute(
        SQL(
            """
            WITH missing AS (
                SELECT line.id,
                       COALESCE(
                           (SELECT manual_line.payment_account_id
                              FROM account_payment_method_line manual_line
                              JOIN account_payment_method manual_method
                                ON manual_method.id = manual_line.payment_method_id
                             WHERE manual_line.journal_id = line.journal_id
                               AND manual_method.code = %(manual_code)s
                               AND manual_line.payment_account_id IS NOT NULL
                             ORDER BY manual_method.payment_type = method.payment_type DESC, manual_line.id
                             LIMIT 1),
                           journal.default_account_id
                       ) AS account_id
                  FROM account_payment_method_line line
                  JOIN account_payment_method method ON method.id = line.payment_method_id
                  JOIN account_journal journal ON journal.id = line.journal_id
                 WHERE line.payment_account_id IS NULL
                   AND method.code = %(batch_code)s
            )
            UPDATE account_payment_method_line line
               SET payment_account_id = missing.account_id
              FROM missing
             WHERE line.id = missing.id
               AND missing.account_id IS NOT NULL
            """,
            batch_code="batch_payment",
            manual_code="manual",
        )
    )
    _logger.info(
        "Backfilled %s batch deposit payment method lines with the manual method or journal default account",
        cr.rowcount,
    )
