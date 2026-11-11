import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/helpdesk_stock_ux/20.0.1.0.0/post-migration.py, on the other side of the pass.
BACKUP_TABLE = "helpdesk_ticket_product_lot_bu"
# 20.0 is the jump where helpdesk_stock drops the two fields. No ceiling on purpose: a later
# jump that keeps the module needs its own consumer, and losing the data is worse than a
# table nobody reads.
FIRST_TARGET_VERSION = 20
COLUMNS = ("product_id", "lot_id")


def migrate(cr, version):
    """Back up the product and the lot of the tickets before the database is sent to Odoo.

    helpdesk_stock defines helpdesk.ticket.product_id and lot_id up to 19.0 and drops them in
    20.0, so Odoo's upgrade runs without them and the two columns go away. 13 of the 23
    databases with helpdesk_stock_ux carry about 21.000 tickets with one of the two loaded,
    and the module defines them again in 20.0: the values have to cross the pass in a table
    Odoo does not look at.

    Only backs up. Plain SQL on purpose: this runs on the old database, with the Odoo of the
    source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. The pre_odoo runs on the whole database: the module is checked here.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["helpdesk_stock_ux"]):
        return

    # The columns come from helpdesk_stock, not from our module: a source version that does
    # not define them is not a failure, there is just nothing to carry over.
    cr.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'helpdesk_ticket' AND column_name IN %s",
        (COLUMNS,),
    )
    found = {row[0] for row in cr.fetchall()}
    if found != set(COLUMNS):
        _logger.info("helpdesk_ticket has no %s: nothing to back up", ", ".join(sorted(set(COLUMNS) - found)))
        return

    _logger.info("Backing up the product and the lot of the tickets into %s", BACKUP_TABLE)
    rows = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, product_id, lot_id
          FROM helpdesk_ticket
         WHERE product_id IS NOT NULL
            OR lot_id IS NOT NULL
        """,
    )
    _logger.info("%s tickets backed up into %s", rows, BACKUP_TABLE)
