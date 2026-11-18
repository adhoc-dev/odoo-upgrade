import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Set the withholding mode of the migrated payments and refresh what their header shows.

    In 20 the amount of a payment is the gross one and ``withhold`` says what the payment does with
    it. The column is new, and Odoo computes it while payment pro loads, when the payments do not
    have their 20 withholding lines yet, so every one of them would stay as a plain payment. The
    lines arrive with the post-migration of l10n_ar_tax, which also turns the amounts into gross
    ones, so this runs as an end-migration, after every post.

    The net amount is not stored (it is computed from the amount and the lines), so there is nothing
    to load for it.
    """
    _logger.info("Running end-migration for account_payment_pro version %s", version)

    if not util.table_exists(cr, "account_payment_withholding_line"):
        _logger.info("No withholding lines in this database, nothing to do")
        return

    # payment / withhold / withhold_pay, the same rule the model computes for a new payment
    cr.execute(
        """
        WITH withheld AS (
            SELECT payment_id, SUM(amount) AS total
              FROM account_payment_withholding_line
             GROUP BY payment_id
        )
        UPDATE account_payment p
           SET withhold = CASE
                   WHEN ROUND((p.amount - w.total)::numeric, cur.decimal_places) = 0 THEN 'withhold'
                   ELSE 'withhold_pay'
               END
          FROM withheld w, res_currency cur
         WHERE p.id = w.payment_id
           AND cur.id = p.currency_id
        """
    )
    with_lines = cr.rowcount
    cr.execute("UPDATE account_payment SET withhold = 'payment' WHERE withhold IS NULL")
    _logger.info("Withholding mode set on %s payments with lines, %s without", with_lines, cr.rowcount)

    # The header of a draft shows the net amount in company currency; with the gross amount loaded by
    # l10n_ar_tax its stored value is the old one. A posted payment reads its entry, so it is left alone.
    cr.execute(
        """
        SELECT DISTINCT p.id
          FROM account_payment p
          JOIN account_payment_withholding_line w ON w.payment_id = p.id
         WHERE p.state = 'draft'
        """
    )
    drafts = [row[0] for row in cr.fetchall()]
    if drafts:
        util.recompute_fields(cr, "account.payment", ["amount_company_currency_signed"], ids=drafts)
    _logger.info("Company currency amount recomputed on %s draft payments with withholdings", len(drafts))
