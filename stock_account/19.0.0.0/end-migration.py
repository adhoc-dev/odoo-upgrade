"""Action points of the new stock valuation, for the customer note.

Upgrade line 2021 computes these over the already migrated database, through odooly; here
the upgrade process itself computes them and leaves them with ``add_customer_note``.

Only the two scenarios the note's message names today (B and D); A and C stay on the
upgrade line, for internal use. This is an ``end-migration`` and not a ``post-`` one
because the rows come from ``purchase`` and ``sale``: ``end-`` scripts run once the whole
graph is updated.

The keys of the values are the variable names the message renders, so they stay in
Spanish: renaming them here would silently empty the note.
"""

import logging

from odoo.upgrade import util

from odoo.upgrade.oba import add_customer_note

_logger = logging.getLogger(__name__)

SLUG = "valoracion-stock-accionables"

# Only tracked products with automatic valuation and a price: on the rest the valuation
# change leaves nothing to review.
EXTRA_FILTERS = [
    ("product_id.is_storable", "=", True),
    ("product_id.categ_id.property_valuation", "=", "real_time"),
    ("price_unit", ">", 0),
]


def migrate(cr, version):
    env = util.env(cr)

    values = {
        "escenario_b_rows": _invoiced_not_received(cr, env),
        "escenario_d_rows": _invoiced_not_delivered(cr, env),
    }

    # Emitted even when both lists come back empty. Emitting only on findings would leave
    # the previous run's values standing on a run that no longer finds any; with an empty
    # message the note archives itself instead.
    add_customer_note(cr, SLUG, values)
    _logger.info(
        "Stock valuation: %s purchase and %s sale lines to review",
        len(values["escenario_b_rows"]),
        len(values["escenario_d_rows"]),
    )


def _invoiced_not_received(cr, env):
    """Scenario B: the purchase was invoiced but the goods have not arrived yet."""
    if not util.module_installed(cr, "purchase"):
        return []
    return [
        {
            "orden": line.order_id.name,
            "contacto": line.order_id.partner_id.name,
            "producto": line.product_id.name,
            "cantidad": line.product_qty,
            "recibido": line.qty_received,
            "facturado": line.qty_invoiced,
            "precio": line.price_unit,
            "importe": line.price_subtotal,
        }
        for line in env["purchase.order.line"].search([("prepaid_expense", "=", True)] + EXTRA_FILTERS)
    ]


def _invoiced_not_delivered(cr, env):
    """Scenario D: the sale was invoiced but the goods have not left yet."""
    if not util.module_installed(cr, "sale"):
        return []
    return [
        {
            "orden": line.order_id.name,
            "cliente": line.order_id.partner_id.name,
            "descripcion": line.name,
            "cantidad": line.product_uom_qty,
            "entregado": line.qty_delivered,
            "facturado": line.qty_invoiced,
            "precio": line.price_unit,
            "importe": line.price_subtotal,
        }
        for line in env["sale.order.line"].search([("deferred_revenue", "=", True)] + EXTRA_FILTERS)
    ]
