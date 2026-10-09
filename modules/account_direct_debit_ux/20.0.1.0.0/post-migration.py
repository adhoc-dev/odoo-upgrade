import logging

from odoo.tools import SQL

from oba import add_customer_note

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
            UPDATE res_partner_bank b
               SET allow_out_payment = TRUE
              FROM res_partner p
             WHERE p.id = b.partner_id
               AND NOT COALESCE(b.allow_out_payment, FALSE)
               AND b.id IN (
                   SELECT partner_bank_id
                     FROM account_direct_debit_mandate
                    WHERE partner_bank_id IS NOT NULL
               )
         RETURNING p.name
            """
        )
    )
    partners = sorted({name for (name,) in cr.fetchall()})
    add_customer_note(
        cr,
        {
            "direct_debit_trusted_accounts_total": len(partners),
            "direct_debit_trusted_accounts_partners": partners[:50],
        },
    )
