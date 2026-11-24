"""Open a task for the preprinted delivery slip templates that do not work in the new version.

A picking type with a ``Plantilla del Remito`` (``l10n_ar_delivery_report_view_id`` of
``l10n_ar_preprinted_template``) prints its preprinted slip with that QWeb view. The
customer or a consultant made it in the database, so no module of ours migrates it, and
the standard slip it relies on changes between versions. If it breaks, the slip does not
print ("Template not found" when the upgrade left the view inactive) and the customer finds
out when somebody tries.

Each template of a preprinted picking type is checked as it will be used:

- the view is active;
- Odoo's own view check passes (``_upgrade_original_check_xml``: ``pre-0-disable-check-views``
  only delays the real one);
- the standard slip renders with it, for the last pickings of those types. A QWeb view from
  scratch can combine and compile and still fail on a field that moved, so only rendering
  tells. Without a picking to render, the first two checks are all there is.

A template fails when every sample picking fails with it: one that fails only with some is a
data problem, not a template one, and is only logged. Nothing is written in the customer's
database; each render is rolled back.

For the ones that fail, a ``project.task`` is created in the project of the upgrade ticket,
as the upgrade line 768 does for the Aeroo reports, in a test and a production request
alike: one task per request, so a ticket with both gets two. The provider cannot set the
upgrade ticket on the task yet (a request marker is replaced only as a whole value of a
field, not inside the commands of ``ticket_ids``), so the task carries that warning.

Only on the last request of a series: the check has to be against the version the customer
ends in. In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded,
and after ``end-210``.
"""

import contextlib
import logging
from html import escape

from odoo import release
from odoo.tools import mute_logger
from odoo.upgrade import util
from oba import UPGRADE_PROJECT, create_record_provider, log_message, should_run, timed

_logger = logging.getLogger(__name__)

FIRST_TARGET_VERSION = 20
MODULE = "l10n_ar_preprinted_template"
# The slip that calls the template of the picking type, in l10n_ar_stock_ux.
REPORT = "stock.action_report_delivery"
# Pickings to render each template with, the last ones of its types.
SAMPLE_SIZE = 3
# Only the standard slip of this version decides the template name; the counting context
# makes the picking print as preprinted without a delivery guide number.
RENDER_CONTEXT = {"l10n_ar_counting": True}
MUTED_LOGGERS = (
    "odoo.addons.base.models.ir_qweb",
    "odoo.addons.base.models.ir_actions_report",
    "odoo.addons.base.models.ir_ui_view",
)
# Constant: a retried callback does not create the task again.
TASK_REF = "preprinted_remito_templates_task"

# What the upgrade line 768 sets on its task.
PLANNING_STAGE = 851  # Planificación
UPGRADE_PRODUCT = 4  # Actualización de Versión
PERSONALIZATION_TAG = 773  # Personalizacion

# Only preprinted types use the template: in the others it is ignored, so it cannot fail.
TEMPLATES = """
    SELECT view.id, array_agg(picking_type.id ORDER BY picking_type.id)
      FROM stock_picking_type picking_type
      JOIN ir_ui_view view ON view.id = picking_type.l10n_ar_delivery_report_view_id
     WHERE picking_type.active
       AND picking_type.l10n_ar_voucher_print_mode = 'preprinted'
  GROUP BY view.id
  ORDER BY view.id
"""


@timed
def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=[MODULE], position="last"):
        return
    if not util.column_exists(cr, "stock_picking_type", "l10n_ar_delivery_report_view_id"):
        _logger.info("No 'Plantilla del Remito' column in stock_picking_type: nothing to check")
        return

    cr.execute(TEMPLATES)
    templates = cr.fetchall()
    if not templates:
        _logger.info("No picking type with a delivery slip template: nothing to check")
        return

    env = util.env(cr)
    failed = []
    # A template that does not work is expected here and handled: Odoo would log each one as
    # an error with its traceback, and runbot fails a build on a traceback.
    with mute_logger(*MUTED_LOGGERS):
        for view_id, picking_type_ids in templates:
            error = _template_error(env, view_id, picking_type_ids)
            if error:
                failed.append((view_id, picking_type_ids, error))
    if not failed:
        _logger.info("No failure found in the delivery slip templates of %s view(s)", len(templates))
        return

    _report(cr, env, failed)


def _template_error(env, view_id, picking_type_ids):
    """Why the template does not work, or None when it does."""
    view = env["ir.ui.view"].with_context(active_test=False).browse(view_id)
    if not view.active:
        # With it inactive the t-call finds nothing and the slip does not print at all.
        return "La vista está desactivada."
    # pre-0-disable-check-views only delays _check_xml: the original says if a view fails.
    check_xml = getattr(type(view), "_upgrade_original_check_xml", type(view)._check_xml)
    try:
        with env.cr.savepoint():
            check_xml(view)
    except Exception as e:
        return _error_text(e)

    picking_ids = (
        env["stock.picking"]
        .with_context(active_test=False)
        .search([("picking_type_id", "in", picking_type_ids)], limit=SAMPLE_SIZE, order="id desc")
        .ids
    )
    if not picking_ids:
        _logger.info("View %s: no picking to render it with, only the view check ran", view_id)
        return None
    errors = [_render_error(env, picking_id) for picking_id in picking_ids]
    if all(errors):
        return errors[0]
    if any(errors):
        _logger.info("View %s fails only with some pickings, not a template problem: %s", view_id, errors)
    return None


def _render_error(env, picking_id):
    """Why the standard slip does not render with the template for the picking, or None."""
    try:
        # closing: rolled back also when it works, the render must leave nothing behind.
        with contextlib.closing(env.cr.savepoint()):
            env["ir.actions.report"].with_context(**RENDER_CONTEXT)._render_qweb_html(REPORT, [picking_id])
    except Exception as e:
        return _error_text(e)
    return None


def _error_text(error):
    """What failed, for whoever fixes the template: the original error, ``SomeError: message``.

    Odoo wraps a render error, once or twice, in a long message that quotes the template;
    the original one is at the end of the chain.
    """
    while error.__cause__ is not None or (error.__context__ is not None and not error.__suppress_context__):
        error = error.__cause__ or error.__context__
    lines = str(error).strip().splitlines()
    return "%s: %s" % (type(error).__name__, (lines[0] if lines else "")[:300])


def _report(cr, env, failed):
    names = {}
    items = []
    for view_id, picking_type_ids, error in failed:
        view = env["ir.ui.view"].with_context(active_test=False).browse(view_id)
        types = ", ".join(env["stock.picking.type"].browse(picking_type_ids).mapped("display_name"))
        names[view_id] = view.key or view.name
        items.append(
            "<li>Plantilla <b>%s</b> (vista %s), tipos de operación: %s.<br/>%s</li>"
            % (escape(view.name or ""), view_id, escape(types), escape(error))
        )
    _logger.info("Delivery slip templates that do not work: %s", names)

    log_message(
        cr,
        "Plantillas del remito preimpreso que no funcionan en esta versión (vistas %s): se creó una tarea "
        "para adaptarlas." % ", ".join(str(view_id) for view_id, _types, _error in failed),
        "warning",
        module=MODULE,
    )
    create_record_provider(
        cr,
        "project.task",
        {
            "name": "Adaptar plantillas del remito preimpreso a Odoo %s" % release.major_version,
            "project_id": UPGRADE_PROJECT,
            "stage_id": PLANNING_STAGE,
            "user_ids": [[6, 0, []]],
            "adhoc_product_id": UPGRADE_PRODUCT,
            "tag_ids": [[6, 0, [PERSONALIZATION_TAG]]],
            "description": (
                "<p>Después de actualizar, estas plantillas propias del remito preimpreso no funcionan. "
                "Hay que adaptarlas al remito estándar de esta versión antes de que el cliente imprima: "
                "con el error que sigue, el remito no sale.</p><ul>%s</ul>"
                "<p>Esta tarea no quedó vinculada al ticket de actualización: vincularla a mano.</p>"
            )
            % "".join(items),
        },
        ref=TASK_REF,
    )
