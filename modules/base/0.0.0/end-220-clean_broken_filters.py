"""Clean the favorites (ir.filters) that use fields missing in the upgraded database.

The fields are checked against the registry, not against a list: a field that left with a
discontinued module, or that a jump removed, is cleaned without one script per case.
upgrade-util has nothing that finds them; the cleaning uses the pieces util.remove_field
uses: the condition on the field leaves the domain, and the field leaves the group by, the
order, the pivot and graph keys, and the sort.

Only the broken filters are written, one by one: no other domain (actions, rules, views)
is touched, and a filter that fails does not stop the others. A filter left without any
real condition is archived: kept as is it would show every record (AND) or none (OR). A
filter it cannot read, or of a model that is gone, is reported and left as is.
A filter of ``_unknown`` counts as one of a model that is gone: upgrade-util moves there the
filters of the customer when a jump removes their model.

In ``modules/base/0.0.0`` so it runs after the modules are loaded and after the renames of
the other scripts. Only on the last jump of a series: on an intermediate database a field
can be missing just because its module has no code in that version, and the cleaning is
for good.
"""

import ast
import json
import logging

from odoo.upgrade import util

from oba import log_message, should_run

try:
    from odoo.orm.domains import CONDITION_OPERATORS
except ImportError:
    # Before 19: the file is loaded on every jump, but should_run stops it there.
    CONDITION_OPERATORS = ()

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 1118.
FIRST_TARGET_VERSION = 20

# "<>" and "==" left the operators in 20, but a favorite from before can still use them.
TERM_OPERATORS = set(CONDITION_OPERATORS) | {"<>", "=="}
SUB_DOMAIN_OPERATORS = {"any", "not any", "any!", "not any!"}
LIST_CONTEXT_KEYS = (
    "group_by", "pivot_measures", "pivot_column_groupby", "pivot_row_groupby", "graph_groupbys", "orderedBy",
)


def _resolve(env, model_name, path):
    """((model, field) where the path breaks, comodel of the last field or None)."""
    model = env[model_name]
    for segment in path.split(":")[0].split("."):
        field = model._fields.get(segment)
        if field is None:
            return (model._name, segment), None
        if not field.relational:
            # date.year_number, properties.x: the rest is not a field
            return None, None
        model = env[field.comodel_name]
    return None, model._name


def _broken_path(env, model_name, path):
    return _resolve(env, model_name, path)[0]


def _domain_leaves(node, model_name, env):
    """(model, path) of every leaf, sub-domains of any included; values are not read."""
    if isinstance(node, (ast.List, ast.Tuple)):
        elts = node.elts
        if (
            len(elts) == 3
            and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts[:2])
            and elts[1].value in TERM_OPERATORS
        ):
            yield model_name, elts[0].value
            if elts[1].value in SUB_DOMAIN_OPERATORS:
                comodel = _resolve(env, model_name, elts[0].value)[1]
                if comodel:
                    yield from _domain_leaves(elts[2], comodel, env)
            return
        for elt in elts:
            yield from _domain_leaves(elt, model_name, env)
        return
    for child in ast.iter_child_nodes(node):
        yield from _domain_leaves(child, model_name, env)


def _domain_breaks(env, model_name, domain):
    leaves = list(_domain_leaves(ast.parse(domain or "[]", mode="eval"), model_name, env))
    breaks = {_broken_path(env, m, p) for m, p in leaves}
    breaks.discard(None)
    return leaves, breaks


def _context_paths(context):
    """Field paths of the context keys util cleans, as util matches them."""
    paths = set()
    if not isinstance(context, dict):
        return paths
    for key in LIST_CONTEXT_KEYS:
        values = context.get(key) or []
        if isinstance(values, str):
            values = [values]
        for value in values:
            if key == "orderedBy" and isinstance(value, dict):
                value = value.get("name")
            if isinstance(value, str):
                paths.add(value.split(":")[0])
    for view_type in ("pivot", "graph", "cohort"):
        measure = context.get("%s_measure" % view_type)
        if isinstance(measure, str):
            paths.add(measure.split(":")[0])
        paths |= _context_paths(context.get(view_type))
    return {p for p in paths if p and not p.startswith("__")}


def _sort_path(item):
    # "name", "name desc", "name asc nulls last", "-name" (descending, old format)
    words = str(item).split()
    return words[0].lstrip("-") if words else ""


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, position="last"):
        return
    try:
        # Private helpers of util.remove_field: applied here to the broken filters only.
        from odoo.upgrade.util.domains import _adapt_one_domain
        from odoo.upgrade.util.fields import _remove_field_from_context, _rm_field_adapter
    except ImportError as e:
        log_message(cr, "Favorites with missing fields not cleaned, upgrade-util changed: %s" % e, "warning")
        return
    _logger.info("Cleaning favorites that use fields missing in this database")

    env = util.env(cr)
    fixed, archived, orphan, not_parsed, not_cleaned = [], [], [], [], []
    cr.execute("SELECT id, model_id, domain, context, sort FROM ir_filters ORDER BY id")
    for filter_id, model_name, domain, context_s, sort_s in cr.fetchall():
        if model_name == "_unknown" or model_name not in env:
            orphan.append((filter_id, model_name))
            continue
        try:
            leaves, domain_breaks = _domain_breaks(env, model_name, domain)
            # Literal only: a context with expressions (uid, ...) cannot be written back.
            context = ast.literal_eval(context_s or "{}")
            sort = json.loads(sort_s or "[]")
        except (SyntaxError, ValueError, TypeError):
            not_parsed.append(filter_id)
            continue
        context_breaks = {p for p in _context_paths(context) if _broken_path(env, model_name, p)}
        # "__count desc": a grouped list sorted by the count, not a field.
        sort_breaks = {
            p for p in map(_sort_path, sort) if p and not p.startswith("__") and _broken_path(env, model_name, p)
        }
        if not (domain_breaks or context_breaks or sort_breaks):
            continue

        missing = sorted({"%s.%s" % b for b in domain_breaks} | context_breaks | sort_breaks)
        try:
            with cr.savepoint():
                new_domain = domain
                for owner_model, field_name in sorted(domain_breaks):
                    new_domain = _adapt_one_domain(
                        cr, owner_model, field_name, "ignored", model_name, new_domain,
                        adapter=_rm_field_adapter, force_adapt=True,
                    )
                    if new_domain is None:
                        raise ValueError("util could not adapt the domain on %s.%s" % (owner_model, field_name))
                new_leaves, still_broken = _domain_breaks(env, model_name, new_domain)
                if still_broken:
                    raise ValueError("the domain still uses %s" % sorted(still_broken))

                if isinstance(context.get("group_by"), str):
                    context["group_by"] = [context["group_by"]]
                for path in context_breaks:
                    _remove_field_from_context(context, path)
                new_context = str(context) if context_breaks else context_s
                new_sort = json.dumps([i for i in sort if _sort_path(i) not in sort_breaks]) if sort_breaks else sort_s

                # It had conditions and none is left: only constant leaves remain.
                archive = bool(leaves) and not new_leaves
                cr.execute(
                    """
                    UPDATE ir_filters
                       SET domain = %s, context = %s, sort = %s, active = active AND NOT %s
                     WHERE id = %s
                    """,
                    (new_domain, new_context, new_sort, archive, filter_id),
                )
        except Exception as e:
            _logger.warning("Could not clean the favorite %s (%s): %s", filter_id, model_name, e)
            not_cleaned.append((filter_id, model_name, missing))
            continue
        (archived if archive else fixed).append((filter_id, model_name, missing))

    if fixed:
        log_message(cr, "Favorites cleaned of fields missing in this database: %s" % fixed, "info")
    if archived:
        log_message(cr, "Favorites archived, no condition was left: %s" % archived, "info")
    if orphan:
        log_message(cr, "Favorites of models missing in this database, not touched: %s" % orphan, "warning")
    if not_parsed:
        log_message(cr, "Favorites that could not be read, not touched: %s" % not_parsed, "warning")
    if not_cleaned:
        log_message(cr, "Favorites with missing fields that could not be cleaned: %s" % not_cleaned, "warning")
