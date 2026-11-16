import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Deja cada proveedor de pago con una sola línea de método electrónico.

    En 18 un proveedor puede quedar en líneas de varios diarios. La 19 no lo acepta:
    `_check_payment_method_line_ids_multiplicity` falla al crear o editar un diario de
    la compañía del proveedor, y la upgrade line 2351 mueve la primera línea del
    proveedor a su diario aunque ya haya otra ahí.

    Se queda la línea con el pago más reciente (la que se usa hoy); las demás pasan al
    método manual del mismo tipo y sin proveedor, igual que sus pagos. Las líneas que
    ya tienen un método distinto al del proveedor no se tocan.

    Es idempotente: una segunda corrida no encuentra proveedores con más de una línea.
    """
    _logger.info("Running 'account_payment_provider_single_method_line.py' script for version %s", version)

    if not util.column_exists(cr, "account_payment_method_line", "payment_provider_id"):
        _logger.info("account_payment is not installed, nothing to do")
        return

    cr.execute(
        SQL(
            """
            WITH provider_lines AS (
                SELECT line.id,
                       method.payment_type,
                       count(*) OVER (PARTITION BY line.payment_provider_id) AS lines_count,
                       row_number() OVER (
                           PARTITION BY line.payment_provider_id
                               ORDER BY last_payment.date DESC NULLS LAST,
                                        last_payment.id DESC NULLS LAST,
                                        line.sequence,
                                        line.id
                       ) AS position
                  FROM account_payment_method_line line
                  JOIN account_payment_method method ON method.id = line.payment_method_id
                  JOIN payment_provider provider
                    ON provider.id = line.payment_provider_id
                   AND provider.code = method.code
             LEFT JOIN LATERAL (
                           SELECT payment.date, payment.id
                             FROM account_payment payment
                            WHERE payment.payment_method_line_id = line.id
                         ORDER BY payment.date DESC, payment.id DESC
                            LIMIT 1
                       ) last_payment ON TRUE
                 WHERE line.journal_id IS NOT NULL
            )
            UPDATE account_payment_method_line line
               SET payment_method_id = manual.id,
                   payment_provider_id = NULL
              FROM provider_lines
              JOIN account_payment_method manual
                ON manual.code = 'manual'
               AND manual.payment_type = provider_lines.payment_type
             WHERE line.id = provider_lines.id
               AND provider_lines.lines_count > 1
               AND provider_lines.position > 1
         RETURNING line.id, line.journal_id
            """
        )
    )
    changed = cr.fetchall()
    if not changed:
        return
    _logger.info(
        "Moved %s payment method lines to the manual method, without provider (line, journal): %s",
        len(changed),
        changed,
    )

    cr.execute(
        SQL(
            """
            UPDATE account_payment payment
               SET payment_method_id = line.payment_method_id
              FROM account_payment_method_line line
             WHERE line.id = payment.payment_method_line_id
               AND line.id IN %(line_ids)s
               AND payment.payment_method_id != line.payment_method_id
            """,
            line_ids=tuple(line_id for line_id, _journal_id in changed),
        )
    )
    _logger.info("Updated the payment method of %s payments", cr.rowcount)
