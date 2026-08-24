import ast
import logging

from odoo.fields import Domain
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Arity of the domain prefix operators, used to walk a domain without evaluating it.
OPERATORS = {"!": 1, "&": 2, "|": 2}


def _negate_literal(raw):
    """Negate a domain whose every element is a literal.

    Returns the negated domain as a string, or None when `raw` is not a plain
    literal domain (it may carry dynamic expressions, see `_negate_source`).
    """
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, (list, tuple)) or not parsed:
        return None
    # Domain normalizes the implicit AND and applies De Morgan, so the stored
    # value stays readable in the `domain` widget.
    return str(~Domain(list(parsed)))


def _negate_source(raw):
    """Negate a domain textually, keeping every element's source verbatim.

    Used when the domain holds dynamic expressions: the field is rendered with
    ``allow_expressions: True``, so it may contain ``context_today()`` or
    ``relativedelta(...)``. Those must NOT be evaluated here, that would freeze
    them into the migration date. Returns a string, or None when the value is
    not a well formed prefix domain.
    """
    try:
        node = ast.parse(raw.strip(), mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return None

    # Walk the prefix notation to count the top level expressions joined by the
    # implicit AND: normalize(d) == ['&'] * (k - 1) + d
    extra_ands = 0
    expected = 1
    for elt in node.elts:
        if expected == 0:
            extra_ands += 1
            expected = 1
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            if elt.value not in OPERATORS:
                return None
            expected += OPERATORS[elt.value] - 1
        else:
            expected -= 1
    if expected != 0:
        return None

    segments = [ast.get_source_segment(raw, elt) for elt in node.elts]
    if any(segment is None for segment in segments):
        return None

    # A single fully negated domain: negating it again just drops the '!'.
    if not extra_ands and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "!":
        return "[%s]" % ", ".join(segments[1:])
    return "[%s]" % ", ".join(["'!'"] + ["'&'"] * extra_ands + segments)


def migrate(cr, version):
    """Invert `sale_order_type.invoice_validate_domain` to preserve v18 behaviour.

    `sale_order_type_automation` flipped the meaning of the field when invoice
    exclusion was added:

    * v18: ``invoices.filtered_domain(domain)`` -> the invoices matching the
      domain are the ones being validated;
    * v19: ``invoices - invoices.filtered_domain(domain)`` -> the invoices
      matching the domain are the ones left in draft.

    Values stored by the client still carry the v18 meaning, so without this the
    automatic invoice validation starts working exactly the other way around,
    with no error and no warning. `sale_gathering_automation` reads the same
    field and got the same flip, so it is covered here as well.

    Empty domains are left alone: they mean "validate everything" in both
    versions, and negating one would match nothing.
    """
    if not util.module_installed(cr, "sale_order_type_automation"):
        return
    if not util.column_exists(cr, "sale_order_type", "invoice_validate_domain"):
        return

    # Records seeded by the upgrade e2e (testing_pre_odu of this repo) include
    # an unparseable domain on purpose, to exercise the preservation branch.
    # Only real client data deserves the WARNING below (it is the signal for a
    # manual review); on the seeded case it would paint every e2e build 'warn'.
    # The 'upgrade_prepare_demo' xmlids only exist on runbot-seeded databases.
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'upgrade_prepare_demo' AND model = 'sale.order.type'
        """
    )
    seeded_ids = {row[0] for row in cr.fetchall()}

    cr.execute(
        """
        SELECT id, invoice_validate_domain
        FROM sale_order_type
        WHERE invoice_validate_domain IS NOT NULL
          AND btrim(invoice_validate_domain) NOT IN ('', '[]')
        ORDER BY id
        """
    )

    for type_id, raw in cr.fetchall():
        try:
            negated = _negate_literal(raw)
        except (ValueError, SyntaxError, TypeError):
            # Not a plain literal: it carries dynamic expressions.
            negated = _negate_source(raw)
        except Exception:
            negated = None

        if not negated:
            log = _logger.info if type_id in seeded_ids else _logger.warning
            log(
                "sale.order.type %s: could not invert invoice_validate_domain %r. "
                "It keeps the old meaning and has to be reviewed by hand.%s",
                type_id,
                raw,
                " (seeded e2e case: preserved on purpose)" if type_id in seeded_ids else "",
            )
            continue

        cr.execute(
            "UPDATE sale_order_type SET invoice_validate_domain = %s WHERE id = %s",
            (negated, type_id),
        )
        _logger.info(
            "sale.order.type %s: invoice_validate_domain %r -> %r", type_id, raw, negated
        )
