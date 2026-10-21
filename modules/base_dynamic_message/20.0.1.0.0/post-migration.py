import ast
import logging

from odoo.upgrade import util

from oba import add_customer_note, log_message

_logger = logging.getLogger(__name__)

LOGICAL = {"&", "|", "!"}


def _field_paths(domain):
    """The field paths of the conditions of a stored domain, without evaluating it.

    The domain may carry "EXP: ..." strings as values, so it is walked as a
    syntax tree. Returns None when it does not parse.
    """
    try:
        node = ast.parse(domain, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    paths = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and elt.value in LOGICAL:
            continue
        if isinstance(elt, (ast.List, ast.Tuple)) and elt.elts:
            first = elt.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                paths.append(first.value)
    return paths


def _missing_path(env, model, path):
    """The first part of ``path`` that does not exist from ``model`` in 20, or None."""
    current = env[model]
    for name in path.split("."):
        field = current._fields.get(name)
        if field is None:
            return name
        if not field.relational:
            return None
        current = env[field.comodel_name]
    return None


def migrate(cr, version):
    """List the dynamic messages that 20 cannot show and nobody can fix by script.

    The pre-migration fixes the operators. What remains needs a person: a
    condition on a field that 20 removed (``res.partner.company_type``, say)
    raises "Invalid field" and breaks the form of the model; a message on a
    model that is gone; and a message whose generated or inherited view is no
    longer active. Removing the condition changes which records show the
    message, so the script only reports. The list goes to the request log and
    to the customer note data (``mensajes_dinamicos_a_revisar``).
    """
    _logger.info("Running post-migration of base_dynamic_message for version %s", version)
    env = util.env(cr)

    to_review = []
    for message in env["ir.model.dynamic_message"].with_context(active_test=False).search([]):
        model = message.model_id.model
        problems = []
        if not model or model not in env:
            problems.append("el modelo %s ya no existe" % (model or message.model_id.display_name))
        else:
            for line in message.line_ids.filtered("domain"):
                paths = _field_paths(line.domain)
                if paths is None:
                    problems.append("no se pudo leer el dominio %s" % line.domain)
                    continue
                for path in paths:
                    missing = _missing_path(env, model, path)
                    if missing == path:
                        problems.append("el campo %s ya no existe" % path)
                    elif missing:
                        problems.append("el campo %s (del filtro %s) ya no existe" % (missing, path))
        for label, view in (
            ("la vista que hereda", message.view_to_inherit_id),
            ("la vista del aviso", message.view_id),
        ):
            if view and not view.active:
                problems.append("%s (%s) está desactivada" % (label, view.name))
        if problems:
            to_review.append({"id": message.id, "nombre": message.name, "modelo": model, "problemas": problems})

    if to_review:
        log_message(
            cr,
            "Mensajes dinámicos que en 20 no se van a mostrar o rompen el formulario de su modelo, a revisar: %s"
            % "; ".join("%s (%s): %s" % (m["nombre"], m["modelo"], ", ".join(m["problemas"])) for m in to_review),
            "warning",
        )
    # Emitted also when empty: "nothing to review" is a result the note may want to say.
    add_customer_note(cr, {"mensajes_dinamicos_a_revisar": to_review})
