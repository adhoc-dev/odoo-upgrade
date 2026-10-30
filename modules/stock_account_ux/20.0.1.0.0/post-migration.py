import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Written by the pre-migration of this folder, before the module update dropped previous_value.
BACKUP_COLUMN = "previous_value_bu"
# Only the rows Odoo left empty are filled: its own update may have set these fields already.
NOT_FILLED = (
    "COALESCE(product_value.old_value, 0) = 0 AND COALESCE(product_value.new_value, 0) = 0"
    " AND product_value.old_cost IS NULL AND product_value.new_cost IS NULL"
)


def migrate(cr, version):
    """Fill the Odoo 20 fields of the value adjustments recorded in 19.

    In 19 an adjustment kept the new value in ``value`` and the module kept the value before
    it in ``previous_value`` (``delta`` was their difference). Odoo 20 reads the adjustment
    from ``old_value`` / ``new_value`` for a move and from ``old_cost`` / ``new_cost`` times
    ``quantity`` for a price change, so a row with those fields empty counts as an adjustment
    of zero: the valuation report and the closing leave it out.

    - A move adjustment keeps the sign of its move, as the value of an outgoing move is
      negative in 20.
    - A price change takes the quantity on hand at its date, which is what 19 booked.
    """
    if not util.column_exists(cr, "product_value", BACKUP_COLUMN):
        _logger.info("%s does not exist: no value adjustment to fill", BACKUP_COLUMN)
        return
    env = util.env(cr)
    _fill(cr, lambda row: _get_quantity(env, row))


def _fill(cr, get_quantity):
    _fill_move_adjustments(cr)
    for row in _fill_price_changes(cr):
        if row["new_cost"] == row["old_cost"]:
            continue
        try:
            with cr.savepoint():
                quantity = get_quantity(row)
        except Exception:  # noqa: BLE001
            _logger.warning("No quantity for value adjustment %s: left at zero", row["id"], exc_info=True)
            continue
        cr.execute(
            SQL(
                "UPDATE product_value SET quantity = %(quantity)s, old_value = %(old_cost)s * %(quantity)s,"
                " new_value = %(new_cost)s * %(quantity)s WHERE id = %(id)s",
                quantity=quantity,
                old_cost=row["old_cost"],
                new_cost=row["new_cost"],
                id=row["id"],
            )
        )


def _fill_move_adjustments(cr):
    cr.execute(
        SQL(
            """
            UPDATE product_value
               SET old_value = CASE WHEN move.value < 0 THEN -1 ELSE 1 END
                               * COALESCE(product_value.%(backup)s, 0),
                   new_value = CASE WHEN move.value < 0 THEN -1 ELSE 1 END * product_value.value
              FROM stock_move move
             WHERE move.id = product_value.move_id
               AND %(not_filled)s
            """,
            backup=SQL.identifier(BACKUP_COLUMN),
            not_filled=SQL(NOT_FILLED),
        )
    )
    _logger.info("Filled %s move adjustments", cr.rowcount)


def _fill_price_changes(cr):
    """Fill the unit costs of the price changes and return them, to set their quantity."""
    cr.execute(
        SQL(
            """
            UPDATE product_value
               SET old_cost = COALESCE(product_value.%(backup)s, 0),
                   new_cost = product_value.value
             WHERE product_value.move_id IS NULL
               AND %(not_filled)s
         RETURNING id, product_id, lot_id, company_id, date, old_cost, new_cost
            """,
            backup=SQL.identifier(BACKUP_COLUMN),
            not_filled=SQL(NOT_FILLED),
        )
    )
    rows = cr.dictfetchall()
    _logger.info("Filled %s price changes", len(rows))
    return rows


def _get_quantity(env, row):
    """Quantity on hand when the price changed, as the 19 module booked it."""
    if row["lot_id"]:
        lot = env["stock.lot"].browse(row["lot_id"])
        return lot.with_context(to_date=row["date"], skip_in_progress=True).product_qty
    product = env["product.product"].sudo().browse(row["product_id"]).with_company(row["company_id"])
    return product._with_valuation_context().with_context(to_date=row["date"]).qty_available
