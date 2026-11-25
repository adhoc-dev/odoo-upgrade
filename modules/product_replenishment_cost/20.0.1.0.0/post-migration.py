"""Tell the customer which replenishment cost rule expressions fail in the new database.

A rule line can carry a Python expression that adds to the cost. ``compute_rule`` evaluates
it and, when it fails, swallows the error: the line stops adding to the cost and nobody is
told. Fields an expression may read change between versions (in 20 the vendor line unit
goes from ``product_uom_id`` to ``uom_id``, and ``_select_seller`` returns a dict), so an
expression that worked can start failing without a trace.

Each rule is evaluated as ``compute_rule`` does, with a product that uses it, and the lines
whose expression raises are reported. Expressions that already failed before the jump are
reported too: the note does not say they broke with this version.

Nothing is written on the customer's data. Rules no product uses are skipped: their
expressions never run.
"""

import logging

from odoo.tools.safe_eval import safe_eval
from odoo.upgrade import util

from oba import add_customer_note

_logger = logging.getLogger(__name__)

# A note nobody reads is a note nobody acts on: the total carries the size, the sample the
# shape.
SAMPLE = 50


def _product_using(env, rule):
    """A product the rule is evaluated with, as compute_rule gets it, or nothing."""
    product = env["product.template"].search([("replenishment_cost_rule_id", "=", rule.id)], limit=1)
    if not product:
        product = (
            env["product.supplierinfo"].search([("replenishment_cost_rule_id", "=", rule.id)], limit=1).product_tmpl_id
        )
    return product


def _failing_lines(rule, product):
    """The lines whose expression raises, evaluated in order as compute_rule does."""
    cost = 1.0
    values = {}
    eval_context = rule._get_eval_context(product)
    eval_context.update({"cost": cost, "lines": values})
    failing = []
    for line in rule.item_ids:
        value = cost * (line.percentage_amount / 100.0) + line.fixed_amount
        if line.expr:
            try:
                # An expression can reach the database: a failing query must not abort
                # the whole upgrade transaction.
                with rule.env.cr.savepoint():
                    eval_context.update({"cost_sum": cost})
                    res = safe_eval(str(line.expr), eval_context)
                if isinstance(res, (int, float)):
                    value += res
            except Exception as e:
                failing.append(
                    {
                        "regla": rule.name,
                        "linea": line.name,
                        "expresion": line.expr,
                        "error": str(e)[:200],
                    }
                )
        values[line.name] = value
        if line.add_to_cost:
            cost += value
    return failing


def migrate(cr, version):
    env = util.env(cr)
    rules = env["product.replenishment_cost.rule"].search([("item_ids.expr", "!=", False)])

    failing = []
    for rule in rules:
        product = _product_using(env, rule)
        if not product:
            continue
        failing += _failing_lines(rule, product)

    _logger.info(
        "product_replenishment_cost: %s rules with expressions, %s lines fail",
        len(rules),
        len(failing),
    )

    # Emitted even when empty: the message hides itself on zero.
    add_customer_note(
        cr,
        {
            "product_replenishment_cost_expresiones_con_error_total": len(failing),
            "product_replenishment_cost_expresiones_con_error": failing[:SAMPLE],
        },
    )
