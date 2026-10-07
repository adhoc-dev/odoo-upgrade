import logging

from oba import should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 2285.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Make the payment method lines of a journal unique by name before the database is sent to Odoo.

    Odoo's check_payment_method_line_ids_multiplicity fails when a journal has two lines of
    the same payment method with the same name. The repeated ones get a " - 1", " - 2"...
    suffix, in id order; the first keeps its name.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_run_pre_odoo(cr, FIRST_TARGET_VERSION, modules=["account"]):
        return

    cr.execute(
        """
        WITH duplicates AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY journal_id, payment_method_id, name ORDER BY id) AS rn
              FROM account_payment_method_line
             WHERE journal_id IS NOT NULL
        )
        UPDATE account_payment_method_line l
           SET name = l.name || ' - ' || (d.rn - 1)
          FROM duplicates d
         WHERE l.id = d.id
           AND d.rn > 1
     RETURNING l.id
        """
    )
    renamed = sorted(row[0] for row in cr.fetchall())
    if renamed:
        _logger.info("Renamed %s repeated payment method lines: %s", len(renamed), renamed)
