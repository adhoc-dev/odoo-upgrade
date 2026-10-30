import ast
import logging

from odoo.orm.domains import CONDITION_OPERATORS
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

# Operators that 19 accepted with a deprecation warning and 20 rejects with
# "Invalid operator": the two aliases, and any valid operator in upper case.
ALIASES = {"<>": "!=", "==": "="}
LOGICAL = {"&", "|", "!"}


def _new_operator(op):
    if op in ALIASES:
        return ALIASES[op]
    lower = op.lower()
    if lower != op and lower in CONDITION_OPERATORS:
        return lower
    return None


def _is_str(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_domain(node):
    """A list or tuple made only of conditions and logical operators."""
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return False
    return all(
        (_is_str(elt) and elt.value in LOGICAL) or (isinstance(elt, (ast.List, ast.Tuple)) and len(elt.elts) == 3)
        for elt in node.elts
    )


def normalize_operators(text):
    """Rewrite in ``text`` the operators that 20 no longer accepts.

    ``text`` is a domain or Python code with domains inside (the code the module
    generates calls ``filtered_domain`` with the domain of each line). Only the
    operator of each condition changes; the rest of the text stays as it is, so
    the line, its code and the compute of the field keep matching. A value such
    as ``"IN"`` inside a list is not an operator and is left alone. Returns the
    new text, or None when nothing changes or the text does not parse.
    """
    if not text:
        return None
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # a domain typed with leading spaces only parses as an expression
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            return None
    lines = text.split("\n")
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)

    def offset(lineno, col):
        # ast columns count UTF-8 bytes, not characters
        return starts[lineno - 1] + len(lines[lineno - 1].encode()[:col].decode())

    replacements = []
    for node in ast.walk(tree):
        if not _is_domain(node):
            continue
        for cond in node.elts:
            if not isinstance(cond, (ast.List, ast.Tuple)):
                continue
            field, op = cond.elts[0], cond.elts[1]
            if not (_is_str(field) and _is_str(op)):
                continue
            new = _new_operator(op.value)
            if new:
                start = offset(op.lineno, op.col_offset)
                end = offset(op.end_lineno, op.end_col_offset)
                literal = text[start:end]
                quote = literal[-1]
                # keep a string prefix (u"...") and the quotes as they were
                head = literal[: literal.index(quote) + 1]
                replacements.append((start, end, head + new + quote))
    if not replacements:
        return None
    for start, end, value in sorted(replacements, reverse=True):
        text = text[:start] + value + text[end:]
    return text


def _rewrite(cr, table, column, where=SQL("TRUE")):
    cr.execute(SQL("SELECT id, %s FROM %s WHERE %s", SQL.identifier(column), SQL.identifier(table), where))
    changed = []
    for rec_id, value in cr.fetchall():
        new = normalize_operators(value)
        if new is not None and new != value:
            cr.execute(
                SQL(
                    "UPDATE %s SET %s = %s WHERE id = %s",
                    SQL.identifier(table),
                    SQL.identifier(column),
                    new,
                    rec_id,
                )
            )
            changed.append(rec_id)
    return changed


def migrate(cr, version):
    """Normalize the domain operators that 20 rejects in the dynamic messages.

    19 accepted ``<>``, ``==`` and upper case operators (``IN``, ``ILIKE``) with
    a deprecation warning; 20 raises "Invalid operator". The module copies the
    domain of each line into its ``code`` and into the ``compute`` of the
    manual field ``x_dynamic_message_<id>``, so a single such operator breaks
    the form of the model for every record. The three places are rewritten the
    same way, so they keep matching.
    """
    _logger.info("Running pre-migration of base_dynamic_message for version %s", version)

    lines = _rewrite(cr, "ir_model_dynamic_message_line", "domain")
    codes = _rewrite(cr, "ir_model_dynamic_message_line", "code")
    fields = _rewrite(
        cr,
        "ir_model_fields",
        "compute",
        SQL(
            "state = 'manual' AND id IN (SELECT field_id FROM ir_model_dynamic_message WHERE field_id IS NOT NULL)",
        ),
    )
    if lines or codes or fields:
        _logger.info(
            "Mensajes dinámicos: se cambiaron a la forma de 20 los operadores de dominio en %s líneas, "
            "%s códigos y %s campos calculados",
            len(lines),
            len(codes),
            len(fields),
        )
