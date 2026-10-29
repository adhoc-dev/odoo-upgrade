import logging

from odoo import SUPERUSER_ID
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Up to 19 the module fixed the vendor of the replenishment rules that Odoo creates on its
    # own (OdooBot, manual trigger). In 20 the rule follows the main vendor of the product while
    # it has none: clear the fixed one on those rules. Rules created by a person, or moved to the
    # automatic trigger, keep theirs. write_uid does not tell whether a person changed the vendor:
    # recomputing a stored field also writes it.
    cr.execute(
        SQL(
            """
            UPDATE stock_warehouse_orderpoint
               SET supplier_id = NULL
             WHERE supplier_id IS NOT NULL
               AND create_uid = %(odoobot)s
               AND trigger = 'manual'
            """,
            odoobot=SUPERUSER_ID,
        )
    )
    _logger.info("Cleared the fixed vendor of %s replenishment rules created by OdooBot", cr.rowcount)
