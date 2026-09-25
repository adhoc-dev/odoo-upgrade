import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # use_receiptbook is only computed True for AR: keep it on where receiptbooks are in use,
    # so the payments recompute of this update does not clear their receiptbook_id.
    if not util.column_exists(cr, "res_company", "use_receiptbook"):
        return
    cr.execute(
        """
        UPDATE res_company rc
           SET use_receiptbook = TRUE
         WHERE rc.use_payment_pro IS TRUE
           AND rc.use_receiptbook IS NOT TRUE
           AND EXISTS (
                SELECT 1
                  FROM account_payment ap
                  JOIN account_move am ON am.id = ap.move_id
                 WHERE ap.company_id = rc.id
                   AND ap.receiptbook_id IS NOT NULL
                   AND am.state = 'posted'
                   AND am.date >= CURRENT_DATE - INTERVAL '3 months'
           )
        RETURNING rc.id
        """
    )
    company_ids = [row[0] for row in cr.fetchall()]
    if company_ids:
        _logger.info("Enabled use_receiptbook on companies %s", company_ids)
