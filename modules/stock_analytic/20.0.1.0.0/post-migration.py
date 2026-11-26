"""Tell the customer which draft scraps lost their analytic distribution in the jump to 20.0.

In 19 the distribution of a scrap lives on the scrap and reaches the stock move only when
the scrap is validated. Odoo 20 removes stock.scrap as a model of its own, so the
distribution of the scraps still in draft is lost in the pass. Validated scraps keep it on
their move.

Nothing is restored here: the customer note lists the scraps so the customer loads the
distribution again before validating them.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import add_customer_note

_logger = logging.getLogger(__name__)

# Written by scripts/pre_odoo/190_200/030-stock_analytic_draft_scraps_backup.py, on the
# other side of the pass.
BACKUP_TABLE = "stock_scrap_draft_analytic_bu"


def migrate(cr, version):
    _logger.info("Running post-migration for version %s", version)

    if not util.table_exists(cr, BACKUP_TABLE):
        # Not "no draft scraps": nobody looked. Emitting zero here would tell the customer
        # that nothing was lost without anybody checking it.
        _logger.warning("%s does not exist: nothing reported. Did the pre-odoo script run?", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            SELECT fecha, producto, cantidad, unidad, cuenta_analitica
              FROM %s
          ORDER BY fecha, id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    # The whole list, not a sample: the note asks the customer to fix each one of them.
    # These keys are the ones the message of upgrade line 2693 reads: if they change here,
    # they change there.
    scraps = [
        {
            "fecha": fecha,
            "producto": producto,
            "cantidad": cantidad,
            "unidad": unidad,
            "cuenta_analitica": cuenta or "",
        }
        for fecha, producto, cantidad, unidad, cuenta in cr.fetchall()
    ]

    count = len(scraps)
    # Also with zero: the table was there, so "nothing was lost" is a result.
    add_customer_note(cr, {"scraps_borrador_count": count, "scraps_borrador": scraps})
    _logger.info("%s draft scraps lost their analytic distribution", count)
