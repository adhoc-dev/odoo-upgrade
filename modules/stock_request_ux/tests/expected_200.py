"""State left by the jump to 20 on the lines of stock_request_ux.

post-migration.py of 20.0.1.0.0 gives the move of a backorder the allocation of the move it
comes from, recomputes the quantities of the lines and settles the state of those that 19 left cancelled.
"""

EXPECTED = {
    "stock.request": {
        # Partial delivery: asks for 5, 3 delivered, the other 2 wait in a backorder. Up to 19 that
        # move has no allocation, so the line is cancelled with 0 in progress and 2 cancelled. If it
        # comes out like that, the script did not give the allocation, did not recompute the line or
        # did not reopen it.
        ref("upgrade_prepare_demo.sr_partial_delivery"): {
            "qty_done": 3.0,
            "qty_in_progress": 2.0,
            "qty_cancelled": 0.0,
            "state": "open",
        },
        # The 2 that waited were delivered later and 19 did not count them: the line is cancelled
        # with 3 done. It has to come out with the 5 done and closed; Cancelled would mean that the
        # script counted the delivery but left the state.
        ref("upgrade_prepare_demo.sr_delivered_late"): {
            "qty_done": 5.0,
            "qty_in_progress": 0.0,
            "qty_cancelled": 0.0,
            "state": "done",
        },
        # 3 delivered, 1 more from the backorder and the last one cancelled. 19 counted only the 3,
        # and the 1 cancelled stays cancelled: with the 4 counted the line is done, as stock_request of
        # 20 closes a line that got part and had the rest cancelled. Cancelled would mean that the
        # script left the state.
        ref("upgrade_prepare_demo.sr_partial_then_cancelled"): {
            "qty_done": 4.0,
            "qty_in_progress": 0.0,
            "qty_cancelled": 1.0,
            "state": "done",
        },
        # Preservation: asks for 5 and nothing was delivered, its move already has the allocation.
        # It has to stay as it was: the script only touches moves of a backorder without allocation.
        ref("upgrade_prepare_demo.sr_untouched"): {
            "qty_done": 0.0,
            "qty_in_progress": 5.0,
            "qty_cancelled": 0.0,
            "state": "open",
        },
    },
}
