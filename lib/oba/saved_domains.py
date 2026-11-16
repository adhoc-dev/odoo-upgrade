"""Domains a module keeps as text (a ``Char`` with ``widget="domain"``) and evaluates later.

The upgrade does not touch them, and from 20 on ``Domain`` rejects with a ``ValueError``
what 19 took with a deprecation warning: the operators ``<>``, ``==`` and the ones in
capitals. A condition on a field that the target no longer has fails the same way.

    from oba import domain_missing_fields, fix_domain_operators

    def migrate(cr, version):
        fixed = fix_domain_operators(raw)
        missing = domain_missing_fields(env, "account.move.line", fixed)

Both work on the text and never evaluate the domain: it may hold ``context_today()`` or
``relativedelta()``, and evaluating it here would freeze it at the date of the migration.

Public API: :func:`fix_domain_operators` and :func:`domain_missing_fields`.
"""

import re

# Operators Odoo 20 accepts. 19 also took a few spellings with a deprecation warning.
VALID_OPERATORS = {
    "=", "!=", "<", "<=", ">", ">=", "=?", "=like", "=ilike", "like", "not like", "ilike", "not ilike",
    "in", "not in", "child_of", "parent_of", "any", "not any", "any!", "not any!",
}  # fmt: skip
OPERATOR_SPELLINGS = {"<>": "!=", "==": "="}

# `('field', 'operator'` of a leaf. The value is not read: it may be a dynamic expression.
LEAF = re.compile(
    r"""(?P<head>\(\s*(?P<fq>['"])(?P<field>[\w.]+)(?P=fq)\s*,\s*)(?P<oq>['"])(?P<op>[^'"]*)(?P=oq)"""
)


def _fix_operator(operator):
    if operator in OPERATOR_SPELLINGS:
        return OPERATOR_SPELLINGS[operator]
    lowered = operator.lower()
    if lowered != operator and lowered in VALID_OPERATORS:
        return lowered
    return operator


def fix_domain_operators(raw):
    """Return ``raw`` with the operator spellings Odoo 20 rejects replaced by the valid ones.

    The change is textual on purpose: every other character of the domain stays as the
    customer wrote it, dynamic expressions and values included.
    """

    def replace(match):
        quote = match.group("oq")
        return "%s%s%s%s" % (match.group("head"), quote, _fix_operator(match.group("op")), quote)

    return LEAF.sub(replace, raw)


def _path_exists(env, model_name, path):
    model = env[model_name]
    for name in path.split("."):
        field = model._fields.get(name)
        if field is None:
            return False
        if field.type == "properties":
            return True
        if not field.relational:
            # What follows a plain field is a granularity (`date.month_number`) or a json path.
            return True
        model = env[field.comodel_name]
    return True


def domain_missing_fields(env, model_name, raw):
    """Sorted field paths of ``raw`` that ``model_name`` does not have in the running Odoo."""
    paths = {match.group("field") for match in LEAF.finditer(raw)}
    return sorted(path for path in paths if not _path_exists(env, model_name, path))
