import logging

from odoo import Command

_logger = logging.getLogger(__name__)

MODULE = "upgrade_prepare_demo"
PARTIAL = "sr_partial_delivery"
UNTOUCHED = "sr_untouched"

# Cases of stock_request_ux/20.0.1.0.0/post-migration.py, checked by
# stock_request_ux/tests/expected_200.py:
#   sr_partial_delivery: the line asks for 5 and 3 were delivered. Up to 19 the move that waits
#       for the other 2 has no allocation: the script has to give it one.
#   sr_untouched: the line asks for 5 and nothing was delivered: the script must not change it.


def _storable_product(env, name, route):
    return env["product.product"].create(
        {"name": name, "type": "consu", "is_storable": True, "route_ids": [Command.set(route.ids)]}
    )


def _order(env, warehouse, product):
    return env["stock.request.order"].create(
        {
            "warehouse_id": warehouse.id,
            "location_id": warehouse.lot_stock_id.id,
            "stock_request_ids": [
                Command.create(
                    {
                        "product_id": product.id,
                        "product_uom_id": product.uom_id.id,
                        "product_uom_qty": 5.0,
                        "warehouse_id": warehouse.id,
                        "location_id": warehouse.lot_stock_id.id,
                    }
                )
            ],
        }
    )


def _register(env, name, record):
    env["ir.model.data"].create(
        {"module": MODULE, "name": name, "model": record._name, "res_id": record.id, "noupdate": True}
    )


def migrate(env):
    if "stock.request.order" not in env or "qty_in_progress" not in env["stock.request"]._fields:
        _logger.info("stock_request is not in this database, nothing is seeded")
        return
    if env.ref(f"{MODULE}.{PARTIAL}", raise_if_not_found=False):
        return
    warehouse = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
    resupply = env["stock.location"].create(
        {"name": "Resupply", "usage": "internal", "location_id": warehouse.view_location_id.id}
    )
    route = env["stock.route"].create({"name": "Resupply", "product_selectable": True})
    env["stock.rule"].create(
        {
            "name": "Resupply",
            "route_id": route.id,
            "location_src_id": resupply.id,
            "location_dest_id": warehouse.lot_stock_id.id,
            "action": "pull",
            "picking_type_id": warehouse.int_type_id.id,
            "procure_method": "make_to_stock",
            "warehouse_id": warehouse.id,
        }
    )

    partial_product = _storable_product(env, "Partial delivery", route)
    untouched_product = _storable_product(env, "Untouched", route)
    for product in (partial_product, untouched_product):
        env["stock.quant"].create({"product_id": product.id, "location_id": resupply.id, "quantity": 20.0})

    partial_order = _order(env, warehouse, partial_product)
    partial_order.action_confirm()
    picking = partial_order.picking_ids
    picking.action_assign()
    move = picking.move_ids
    move.quantity = 3.0
    move.picked = True
    env["stock.backorder.confirmation"].with_context(button_validate_picking_ids=[picking.id]).create(
        {"pick_ids": [Command.link(picking.id)]}
    ).process()
    # In 19 the split did not copy the allocation, so the move that waits has none. Making it
    # explicit keeps the case the same in a base where it was born with one.
    pending = picking.backorder_ids.move_ids
    env.cr.execute("DELETE FROM stock_request_allocation WHERE stock_move_id IN %s", (tuple(pending.ids),))
    env.invalidate_all()
    # The stored quantities do not follow a delete by SQL: they have to show what 19 left
    line = partial_order.stock_request_ids
    line._compute_qty()
    line.flush_recordset()
    _register(env, PARTIAL, line)

    untouched_order = _order(env, warehouse, untouched_product)
    untouched_order.action_confirm()
    _register(env, UNTOUCHED, untouched_order.stock_request_ids)
    _logger.info("Seeded two stock request lines for the allocations of the backorders")
