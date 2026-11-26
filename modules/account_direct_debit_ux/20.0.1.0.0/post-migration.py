import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Trust the bank accounts the direct debit mandates collect from.

    In 20.0 validating a mandate asks for a trusted account. Only the mandate accounts: trusting every
    account would also lift Odoo's check on paying vendors.
    """
    _logger.info("Trusting the bank accounts of direct debit mandates")
    cr.execute(
        SQL(
            """
            UPDATE res_partner_bank
               SET allow_out_payment = TRUE
             WHERE NOT COALESCE(allow_out_payment, FALSE)
               AND id IN (
                   SELECT partner_bank_id
                     FROM account_direct_debit_mandate
                    WHERE partner_bank_id IS NOT NULL
               )
            """
        )
    )
    _logger.info("Trusted %s bank accounts of direct debit mandates", cr.rowcount)
