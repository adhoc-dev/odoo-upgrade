import logging

from odoo.tools import float_compare, html_escape
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

QTY_FIELDS = ["qty_done", "qty_in_progress", "qty_cancelled"]
# One level per pass: a pending move that was received in part gives its own pending move
MAX_PASSES = 50

# The move of the backorder takes what its request line still had open on the move it comes
# from. It needs exactly one source move, that nobody else uses, and the request in the unit
# of the product, so no conversion is needed. A pending move has to take all of what was open,
# a done one can take less: the rest went to the next backorder.
CREATE_ALLOCATIONS = """
    WITH target AS (
        SELECT m.id AS move_id,
               m.product_qty,
               m.state,
               bm.id AS source_move_id
          FROM stock_move m
          JOIN stock_picking p ON p.id = m.picking_id
          JOIN stock_move bm ON bm.picking_id = p.backorder_id
                            AND bm.product_id = m.product_id
                            AND bm.state != 'cancel'
         WHERE m.state != 'cancel'
           AND m.origin_returned_move_id IS NULL
           AND NOT EXISTS (SELECT 1 FROM stock_request_allocation x WHERE x.stock_move_id = m.id)
    ),
    paired AS (
        SELECT t.*
          FROM target t
         WHERE (SELECT count(*) FROM target o WHERE o.move_id = t.move_id) = 1
           AND (SELECT count(*) FROM target o WHERE o.source_move_id = t.source_move_id) = 1
    ),
    open_qty AS (
        SELECT p.move_id,
               p.product_qty,
               p.state,
               a.id AS source_allocation_id,
               a.stock_request_id,
               r.company_id,
               a.requested_product_uom_qty - a.allocated_product_qty AS open_qty,
               r.product_uom_id = pt.uom_id AS same_unit
          FROM paired p
          JOIN stock_request_allocation a ON a.stock_move_id = p.source_move_id
          JOIN stock_request r ON r.id = a.stock_request_id
          JOIN product_product pp ON pp.id = r.product_id
          JOIN product_template pt ON pt.id = pp.product_tmpl_id
    ),
    ok_moves AS (
        SELECT move_id
          FROM open_qty
         GROUP BY move_id, product_qty, state
        HAVING bool_and(same_unit)
           AND sum(greatest(open_qty, 0)) > 0
           AND CASE WHEN state = 'done'
                    THEN round(product_qty::numeric, 5) <= round(sum(greatest(open_qty, 0))::numeric, 5)
                    ELSE round(product_qty::numeric, 5) = round(sum(greatest(open_qty, 0))::numeric, 5)
               END
    ),
    to_create AS (
        SELECT o.move_id,
               o.stock_request_id,
               o.company_id,
               o.open_qty,
               CASE WHEN o.state = 'done'
                    THEN greatest(least(o.open_qty,
                                        o.product_qty - coalesce(sum(o.open_qty) OVER (
                                            PARTITION BY o.move_id
                                            ORDER BY o.source_allocation_id
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)),
                                  0)
                    ELSE 0
               END AS allocated_qty
          FROM open_qty o
          JOIN ok_moves k ON k.move_id = o.move_id
         WHERE o.open_qty > 0
    )
    INSERT INTO stock_request_allocation (
        stock_request_id, stock_move_id, company_id,
        requested_product_uom_qty, allocated_product_qty,
        create_uid, create_date, write_uid, write_date
    )
    SELECT stock_request_id, move_id, company_id, open_qty, allocated_qty,
           1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC'
      FROM to_create
    RETURNING stock_request_id
"""

# Same pairing as above, without the checks: what is still orphan after the passes
LEFT_ORPHANS = """
    SELECT DISTINCT m.id
      FROM stock_move m
      JOIN stock_picking p ON p.id = m.picking_id
      JOIN stock_move bm ON bm.picking_id = p.backorder_id
                        AND bm.product_id = m.product_id
                        AND bm.state != 'cancel'
      JOIN stock_request_allocation a ON a.stock_move_id = bm.id
     WHERE m.state != 'cancel'
       AND m.origin_returned_move_id IS NULL
       AND NOT EXISTS (SELECT 1 FROM stock_request_allocation x WHERE x.stock_move_id = m.id)
     ORDER BY m.id
"""


def create_allocations(cr):
    """Give the moves of a backorder the allocation that their source move has.

    Up to 19 the split of a move did not copy its allocations, so the pending move of a partial
    delivery was not part of its request line. Returns the ids of the requests that changed.
    """
    request_ids = set()
    for _ in range(MAX_PASSES):
        cr.execute(CREATE_ALLOCATIONS)
        created = cr.fetchall()
        if not created:
            break
        request_ids.update(request_id for (request_id,) in created)
        _logger.info("Created %s allocations on the moves of backorders", len(created))
    cr.execute(LEFT_ORPHANS)
    left = [move_id for (move_id,) in cr.fetchall()]
    if left:
        _logger.warning(
            "%s moves of backorders were left without allocation, they do not match the quantities of their "
            "source move or the pairing is ambiguous: %s",
            len(left),
            left[:50],
        )
    return sorted(request_ids)


POST_NOTES = """
    INSERT INTO mail_message (
        model, res_id, message_type, subtype_id, author_id, body, date,
        message_id, create_uid, create_date, write_uid, write_date
    )
    SELECT 'stock.request', r.id, 'notification', %(subtype_id)s, %(author_id)s,
           %(body)s, now() AT TIME ZONE 'UTC',
           '<' || md5(random()::text || r.id::text) || '@stock_request_ux.upgrade>',
           1, now() AT TIME ZONE 'UTC', 1, now() AT TIME ZONE 'UTC'
      FROM stock_request r
     WHERE r.id = ANY(%(ids)s)
"""


def post_notes(cr, subtype_id, author_id, request_ids, body):
    """Leave the same internal note on the chatter of each line, in one query."""
    if not request_ids:
        return
    cr.execute(
        POST_NOTES,
        {
            "subtype_id": subtype_id,
            "author_id": author_id,
            "body": "<p>%s</p>" % html_escape(body),
            "ids": list(request_ids),
        },
    )
    _logger.info("Left a note on %s stock requests", cr.rowcount)


def settle_states(env, request_ids):
    """Make the lines that 19 left cancelled follow their quantities again.

    A line was cancelled when its pending move had no allocation, so it asked for more than
    what it counted. Once the allocations are back, a line that got everything is done and one
    with something still to deliver and nothing cancelled is in progress. A line that still has
    something cancelled stays so, as it would after a partial delivery. Returns the ids of the
    lines that are now in progress and of those that are now done.
    """
    lines = env["stock.request"].browse(request_ids).filtered(lambda r: r.state == "cancel")
    precision = env["decimal.precision"].precision_get("Product Unit")
    lines.check_done()
    reopened = lines.filtered(
        lambda r: r.state == "cancel"
        and float_compare(r.qty_cancelled, 0, precision_digits=precision) <= 0
        and float_compare(r.qty_in_progress, 0, precision_digits=precision) > 0
    )
    reopened.write({"state": "open"})
    changed = lines.filtered(lambda r: r.state != "cancel")
    for line in changed:
        _logger.info("Stock request %s was cancelled and is now %s", line.id, line.state)
    return changed.filtered(lambda r: r.state == "open").ids, changed.filtered(lambda r: r.state == "done").ids


def migrate(cr, version):
    request_ids = create_allocations(cr)
    if request_ids:
        # The stored quantities of the lines do not depend on the new rows until they are recomputed
        util.recompute_fields(cr, "stock.request", QTY_FIELDS, ids=request_ids)
        _logger.info("Recomputed the quantities of %s stock requests", len(request_ids))
        env = util.env(cr)
        reopened_ids, done_ids = settle_states(env, request_ids)
        # A note has one language: the one of the company
        request = env["stock.request"].with_context(lang=env.company.partner_id.lang or "en_US")
        subtype_id = util.ref(cr, "mail.mt_note")
        author_id = util.ref(cr, "base.partner_root")
        post_notes(cr, subtype_id, author_id, reopened_ids, request._get_recovered_state_note("open"))
        post_notes(cr, subtype_id, author_id, done_ids, request._get_recovered_state_note("done"))
