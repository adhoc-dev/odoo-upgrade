"""State left by the jump to 20 on the lines of stock_request_ux.

post-migration.py of 20.0.1.0.0 gives the move of a backorder the allocation of the move it
comes from, and recomputes the quantities of the lines.
"""

EXPECTED = {
    "stock.request": {
        # Partial delivery: asks for 5, 3 delivered, the other 2 wait in a backorder. Up to 19 that
        # move has no allocation, so the line shows 0 in progress and 2 cancelled. If it comes out
        # like that, the script did not give the allocation or did not recompute the line.
        ref("upgrade_prepare_demo.sr_partial_delivery"): {
            "qty_done": 3.0,
            "qty_in_progress": 2.0,
            "qty_cancelled": 0.0,
        },
        # Preservation: asks for 5 and nothing was delivered, its move already has the allocation.
        # It has to stay as it was: the script only touches moves of a backorder without allocation.
        ref("upgrade_prepare_demo.sr_untouched"): {
            "qty_done": 0.0,
            "qty_in_progress": 5.0,
            "qty_cancelled": 0.0,
        },
    },
}
