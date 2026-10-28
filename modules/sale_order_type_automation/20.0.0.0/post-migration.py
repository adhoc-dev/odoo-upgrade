import logging
import re

from odoo.tools import SQL
from odoo.upgrade import util
from oba import add_customer_note

_logger = logging.getLogger(__name__)

# Saved domains of sale.order.type and the model each one is evaluated against.
DOMAIN_FIELDS = {
    "invoice_validate_domain": "account.move",
    "sale_order_filter_domain": "sale.order",
}

# Operators Odoo 20 accepts. 19 also took a few spellings with a deprecation warning.
VALID_OPERATORS = {
    "=", "!=", "<", "<=", ">", ">=", "=?", "=like", "=ilike", "like", "not like", "ilike", "not ilike",
    "in", "not in", "child_of", "parent_of", "any", "not any", "any!", "not any!",
}  # fmt: skip
OPERATOR_SPELLINGS = {"<>": "!=", "==": "="}

# `('field', 'operator'` of a leaf. The value is not read: it may be a dynamic expression
# (the widget uses allow_expressions) and must never be evaluated here.
LEAF = re.compile(
    r"""(?P<head>\(\s*(?P<fq>['"])(?P<field>[\w.]+)(?P=fq)\s*,\s*)(?P<oq>['"])(?P<op>[^'"]*)(?P=oq)"""
)

# What the customer note is shown: how many invalid conditions and a sample of them.
SAMPLE_SIZE = 50


def _fix_operator(operator):
    if operator in OPERATOR_SPELLINGS:
        return OPERATOR_SPELLINGS[operator]
    lowered = operator.lower()
    if lowered != operator and lowered in VALID_OPERATORS:
        return lowered
    return operator


def _fix_operators(raw):
    """Return `raw` with the operator spellings Odoo 20 rejects replaced by the valid ones.

    The change is textual on purpose: it keeps every other character of the domain, dynamic
    expressions included, as the client wrote it.
    """

    def replace(match):
        fixed = _fix_operator(match.group("op"))
        quote = match.group("oq")
        return "%s%s%s%s" % (match.group("head"), quote, fixed, quote)

    return LEAF.sub(replace, raw)


def _path_exists(env, model_name, path):
    model = env[model_name]
    for name in path.split("."):
        field = model._fields.get(name)
        if field is None:
            return False
        if field.type == "properties":
            return True
        if field.relational:
            model = env[field.comodel_name]
        else:
            # What follows a plain field is a granularity (`date.month_number`) or a json path.
            return True
    return True


def _missing_fields(env, model_name, raw):
    paths = {match.group("field") for match in LEAF.finditer(raw)}
    return sorted(path for path in paths if not _path_exists(env, model_name, path))


def migrate(cr, version):
    """Make the saved domains of the order types work in Odoo 20.

    `sale.order.type.invoice_validate_domain` and `sale_order_filter_domain` are `Char` fields
    that hold a domain, and the automation evaluates them with `safe_eval` when an order is
    confirmed or a transfer validated, outside any `try`. The upgrade does not touch them, and
    what 19 took with a warning, 20 rejects with a `ValueError`, so an order type that has one
    of them cannot confirm orders:

    * the operators `<>`, `==` and the ones in capitals (`ILIKE`) are rewritten to `!=`, `=`
      and the lowercase one, which mean the same;
    * a condition on a field that no longer exists (`checked`, `require_payment`, ...) has no
      equivalent: it is not touched, because dropping it changes which invoices are validated
      by themselves. It is logged and reported to the customer note so someone fixes it by
      hand.

    The domains are never evaluated: the widget allows `context_today()` or `relativedelta()`
    and evaluating them here would freeze them at the date of the migration.
    """
    if not util.module_installed(cr, "sale_order_type_automation"):
        return
    columns = [
        column
        for column in DOMAIN_FIELDS
        if util.column_exists(cr, "sale_order_type", column)
    ]
    if not columns:
        return

    # Types seeded by the upgrade e2e (tests/pre_odu of this repo) keep an invalid condition on
    # purpose. Only real customer data deserves the WARNING and the customer note.
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'upgrade_prepare_demo' AND model = 'sale.order.type'
        """
    )
    seeded_ids = {row[0] for row in cr.fetchall()}

    env = util.env(cr)
    rewritten = 0
    invalid = []

    for column in columns:
        model_name = DOMAIN_FIELDS[column]
        if model_name not in env:
            _logger.warning(
                "Model %s does not exist: the %s of the order types was not checked",
                model_name,
                column,
            )
            return
        cr.execute(
            SQL(
                """
                SELECT id, %(column)s
                  FROM sale_order_type
                 WHERE %(column)s IS NOT NULL
                   AND btrim(%(column)s) NOT IN ('', '[]')
                 ORDER BY id
                """,
                column=SQL.identifier(column),
            )
        )
        for type_id, raw in cr.fetchall():
            fixed = _fix_operators(raw)
            if fixed != raw:
                cr.execute(
                    SQL(
                        "UPDATE sale_order_type SET %s = %s WHERE id = %s",
                        SQL.identifier(column),
                        fixed,
                        type_id,
                    )
                )
                rewritten += 1
                _logger.info(
                    "sale.order.type %s: %s %r -> %r", type_id, column, raw, fixed
                )

            missing = _missing_fields(env, model_name, fixed)
            if not missing:
                continue
            log = _logger.info if type_id in seeded_ids else _logger.warning
            log(
                "sale.order.type %s: %s %r names fields %s that %s does not have in 20. "
                "The order type cannot confirm orders until someone fixes it by hand.%s",
                type_id,
                column,
                fixed,
                missing,
                model_name,
                " (seeded e2e case: kept on purpose)" if type_id in seeded_ids else "",
            )
            if type_id not in seeded_ids:
                invalid.append((type_id, column, missing))

    names = {
        t.id: t.display_name
        for t in env["sale.order.type"].browse([item[0] for item in invalid])
    }
    # Also with zero: the message can say that nothing is left to fix. Not emitted above only
    # when nobody could look (a model or a column is missing).
    add_customer_note(
        cr,
        {
            "saved_domains_rewritten": rewritten,
            "saved_domains_invalid_total": len(invalid),
            "saved_domains_invalid": [
                {
                    "tipo": names.get(type_id),
                    "campo": column,
                    "campos_inexistentes": missing,
                }
                for type_id, column, missing in invalid[:SAMPLE_SIZE]
            ],
        },
    )
