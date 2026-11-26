import logging

from odoo.tools import float_compare, html_escape
from odoo.upgrade import util

from oba import add_customer_note, timed

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
               m.product_id,
               m.product_qty,
               m.state,
               bm.id AS source_move_id,
               count(*) OVER (PARTITION BY m.id) AS sources,
               count(*) OVER (PARTITION BY bm.id) AS targets
          FROM stock_move m
          JOIN stock_picking p ON p.id = m.picking_id
          JOIN stock_move bm ON bm.picking_id = p.backorder_id
                            AND bm.product_id = m.product_id
                            AND bm.state != 'cancel'
         WHERE p.backorder_id IS NOT NULL
           AND m.state != 'cancel'
           AND m.origin_returned_move_id IS NULL
           AND NOT EXISTS (SELECT 1 FROM stock_request_allocation x WHERE x.stock_move_id = m.id)
           -- only backorders of a request: all the candidates of the move stay, so the counts do not change
           AND EXISTS (
               SELECT 1
                 FROM stock_move rm
                 JOIN stock_request_allocation ra ON ra.stock_move_id = rm.id
                WHERE rm.picking_id = p.backorder_id
                  AND rm.product_id = m.product_id
           )
    ),
    paired AS (
        SELECT *
          FROM target
         WHERE sources = 1
           AND targets = 1
    ),
    -- what each line already has on its moves: delivered on the done ones, asked on the others
    covered AS (
        SELECT o.stock_request_id,
               sum(CASE WHEN om.state = 'done' THEN o.allocated_product_qty
                        ELSE o.requested_product_uom_qty END) AS qty
          FROM stock_request_allocation o
          JOIN stock_move om ON om.id = o.stock_move_id
         -- one pass over the allocations; filtering by the pairs would make them a CTE that the planner
         -- underestimates, and the join with it grows with the square
         GROUP BY o.stock_request_id
    ),
    open_qty AS (
        SELECT p.move_id,
               p.product_qty,
               p.state,
               a.id AS source_allocation_id,
               a.stock_request_id,
               r.company_id,
               -- what was open on the source move, but never more than what the line still asks
               -- after what its other moves cover: a line closed with Cancel remaining asks no more
               least(
                   a.requested_product_uom_qty - a.allocated_product_qty,
                   r.product_uom_qty - a.allocated_product_qty - (
                       c.qty - CASE WHEN sm.state = 'done' THEN a.allocated_product_qty
                                    ELSE a.requested_product_uom_qty END
                   )
               ) AS open_qty,
               r.product_uom_id = pt.uom_id AS same_unit
          FROM paired p
          JOIN stock_request_allocation a ON a.stock_move_id = p.source_move_id
          JOIN stock_move sm ON sm.id = a.stock_move_id
          JOIN covered c ON c.stock_request_id = a.stock_request_id
          JOIN stock_request r ON r.id = a.stock_request_id
                              -- a line of a pack counts the pack, not the component that the move carries
                              AND r.product_id = p.product_id
          JOIN product_product pp ON pp.id = r.product_id
          JOIN product_template pt ON pt.id = pp.product_tmpl_id
    ),
    -- the checks of each move as window functions: a join against the aggregate grows with the square
    scored AS (
        SELECT o.*,
               bool_and(o.same_unit) OVER w AS all_same_unit,
               sum(greatest(o.open_qty, 0)) OVER w AS total_open
          FROM open_qty o
        WINDOW w AS (PARTITION BY o.move_id)
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
          FROM scored o
         WHERE o.all_same_unit
           AND o.total_open > 0
           AND CASE WHEN o.state = 'done'
                    THEN round(o.product_qty::numeric, 5) <= round(o.total_open::numeric, 5)
                    ELSE round(o.product_qty::numeric, 5) = round(o.total_open::numeric, 5)
               END
           AND o.open_qty > 0
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

# Same pairing as above, without the checks: what is still orphan after the passes, with the line
# of its source move and why it was left. A kit line asks for the kit and the move carries its
# component; a closed line already has all it asks (Cancel remaining lowered it to what was delivered).
LEFT_ORPHANS = """
    SELECT DISTINCT ON (m.id)
           m.id,
           r.id,
           CASE WHEN r.product_id != m.product_id THEN 'kit'
                WHEN r.product_uom_qty <= coalesce((
                    SELECT sum(o.allocated_product_qty)
                      FROM stock_request_allocation o
                      JOIN stock_move om ON om.id = o.stock_move_id
                     WHERE o.stock_request_id = r.id
                       AND om.state = 'done'
                ), 0) THEN 'closed'
                ELSE 'unmatched'
           END
      FROM stock_move m
      JOIN stock_picking p ON p.id = m.picking_id
      JOIN stock_move bm ON bm.picking_id = p.backorder_id
                        AND bm.product_id = m.product_id
                        AND bm.state != 'cancel'
      JOIN stock_request_allocation a ON a.stock_move_id = bm.id
      JOIN stock_request r ON r.id = a.stock_request_id
     WHERE m.state != 'cancel'
       AND m.origin_returned_move_id IS NULL
       AND NOT EXISTS (SELECT 1 FROM stock_request_allocation x WHERE x.stock_move_id = m.id)
     ORDER BY m.id, a.id
"""
# How many of the moves left the customer note lists, the total goes apart
SAMPLE_SIZE = 50


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
    return sorted(request_ids)


def left_orphans(cr):
    """The moves of backorders still without allocation: ``(move_id, request_id, reason)``."""
    cr.execute(LEFT_ORPHANS)
    left = cr.fetchall()
    if left:
        _logger.info(
            "%s moves of backorders were left without allocation (kit, closed line or no safe pairing): %s",
            len(left),
            [move_id for move_id, _request_id, _reason in left[:SAMPLE_SIZE]],
        )
    return left


def report_left_orphans(env, left):
    """Leave the moves left without allocation to the customer note, for the customer to review."""
    sample = left[:SAMPLE_SIZE]
    moves = {move.id: move for move in env["stock.move"].browse({row[0] for row in sample})}
    requests = {request.id: request for request in env["stock.request"].browse({row[1] for row in sample})}
    reasons = {"kit": "kit", "closed": "cerrada", "unmatched": "sin_emparejar"}
    # Also with zero: the message can say that nothing is left to review
    add_customer_note(
        env.cr,
        {
            "stock_request_ux_pending_moves_total": len(left),
            "stock_request_ux_pending_moves": [
                {
                    "transferencia": moves[move_id].picking_id.name,
                    "producto": moves[move_id].product_id.display_name,
                    "cantidad": moves[move_id].product_uom_qty,
                    "solicitud": requests[request_id].name,
                    "orden": requests[request_id].order_id.name or "",
                    "motivo": reasons[reason],
                }
                for move_id, request_id, reason in sample
            ],
        },
    )


POST_NOTES = """
    INSERT INTO mail_message (
        model, res_id, message_type, subtype_id, author_id, body, date,
        message_id, create_uid, create_date, write_uid, write_date
    )
    SELECT 'stock.request', r.id, 'comment', %(subtype_id)s, %(author_id)s,
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
    what it counted. Once the allocations are back it follows the rule of stock_request in 20:
    a line with something still to deliver is in progress, and one with nothing left to deliver
    is done if something was delivered, also when the rest was cancelled. Returns the ids of the
    lines that are now in progress, of those that are now done, and of the done ones that still
    have something cancelled.
    """
    lines = env["stock.request"].browse(request_ids).filtered(lambda r: r.state == "cancel")
    precision = env["decimal.precision"].precision_get("Product Unit")
    lines.check_done()
    reopened = lines.filtered(
        lambda r: r.state == "cancel" and float_compare(r.qty_in_progress, 0, precision_digits=precision) > 0
    )
    reopened.write({"state": "open"})
    changed = lines.filtered(lambda r: r.state != "cancel")
    for line in changed:
        _logger.info("Stock request %s was cancelled and is now %s", line.id, line.state)
    done = changed.filtered(lambda r: r.state == "done")
    done_cancelled = done.filtered(lambda r: float_compare(r.qty_cancelled, 0, precision_digits=precision) > 0)
    return changed.filtered(lambda r: r.state == "open").ids, (done - done_cancelled).ids, done_cancelled.ids


def notes_by_lang(env, request_ids):
    """The ids of the lines grouped by the language of their company: a note has one language."""
    by_lang = {}
    for line in env["stock.request"].browse(request_ids):
        lang = line.company_id.partner_id.lang or "en_US"
        by_lang.setdefault(lang, []).append(line.id)
    return by_lang


@timed
def migrate(cr, version):
    _logger.info("Running post-migration for version %s", version)
    # the allocations have no index on the move nor on the line, and every pass looks them up by both
    with util.temp_index(cr, "stock_request_allocation", "stock_move_id"), util.temp_index(
        cr, "stock_request_allocation", "stock_request_id"
    ):
        request_ids = create_allocations(cr)
        left = left_orphans(cr)
    env = util.env(cr)
    report_left_orphans(env, left)
    if request_ids:
        # The stored quantities of the lines do not depend on the new rows until they are recomputed
        util.recompute_fields(cr, "stock.request", QTY_FIELDS, ids=request_ids)
        _logger.info("Recomputed the quantities of %s stock requests", len(request_ids))
        reopened_ids, done_ids, done_cancelled_ids = settle_states(env, request_ids)
        subtype_id = util.ref(cr, "mail.mt_note")
        author_id = util.ref(cr, "base.partner_root")
        # the flag goes only when set, so the other notes do not need the newer stock_request_ux
        for state, flags, ids in (
            ("open", {}, reopened_ids),
            ("done", {}, done_ids),
            ("done", {"cancelled": True}, done_cancelled_ids),
        ):
            for lang, lang_ids in notes_by_lang(env, ids).items():
                note = env["stock.request"].with_context(lang=lang)._get_recovered_state_note(state, **flags)
                post_notes(cr, subtype_id, author_id, lang_ids, note)
