from odoo.upgrade.testing import IntegrityCase


class TestConfirmedSales(IntegrityCase):
    """An upgrade must not change the confirmed sales of any company."""

    message = "Las ventas confirmadas cambiaron en la actualización"

    def invariant(self):
        # Aggregates only: the value travels in the database and has to stay small.
        self.env.cr.execute(
            """
            SELECT company_id, count(*), round(sum(amount_total), 2)::text
              FROM sale_order
             WHERE state = 'sale'
          GROUP BY company_id
          ORDER BY company_id
            """
        )
        return [list(row) for row in self.env.cr.fetchall()]
