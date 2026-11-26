"""Check again the views whose check ``pre-0-disable-check-views.py`` delayed.

With every module loaded, a view that still fails is not a transient error: the fixdb of the
postupgrade would stop the request on it. It goes to the request as a warning, with its
xmlid, so it can be fixed before the fixdb. Nothing is changed: the custom views that fail
are already archived by ``end-210-check_personalizations.py``.

The orphans are left out: ``_process_end`` purges them after every end script, with the same
rule used here (an xmlid of an updated module, not ``noupdate`` and not loaded in this run).

In ``modules/base/0.0.0`` so it runs on every jump, after the other end scripts of ``base``
and before ``end-900``. The end scripts of the other modules run later, in graph order.
"""

import logging

from odoo.upgrade import util
from oba import log_message, should_run, timed

_logger = logging.getLogger(__name__)


@timed
def migrate(cr, version):
    if not should_run(cr, version):
        return
    View = util.env(cr)["ir.ui.view"]
    delayed = getattr(type(View), "_upgrade_delayed_view_ids", set())
    if not delayed:
        return

    views = View.search([("id", "in", list(delayed))]) - _orphans(View, delayed)
    xmlids = views.get_external_id()
    failing = []
    for view in views:
        try:
            with cr.savepoint():
                type(View)._upgrade_original_check_xml(view)
        except Exception as e:
            _logger.warning("View %s still fails: %s", view.id, e)
            # The full error is in the log; the request gets it in one short line.
            error = " ".join(str(e).split())[:200] or type(e).__name__
            failing.append("%s (%s): %s" % (xmlids.get(view.id) or view.id, view.name, error))
    _logger.info("Checked again %s of %s delayed views, %s still fail", len(views), len(delayed), len(failing))
    if failing:
        log_message(
            cr, "Vistas que siguen fallando después de actualizar:\n%s" % "\n".join(failing), "warning", module="base",
        )


def _orphans(View, view_ids):
    """The views among ``view_ids`` that ``_process_end`` is going to purge."""
    cr, registry = View.env.cr, View.pool
    loaded = getattr(registry, "loaded_xmlids", None)
    if not loaded or not registry.updated_modules:
        return View.browse()
    cr.execute(
        """
        SELECT res_id, module || '.' || name
          FROM ir_model_data
         WHERE model = 'ir.ui.view'
           AND res_id = ANY(%s)
           AND module = ANY(%s)
           AND noupdate IS NOT TRUE
        """,
        (list(view_ids), list(registry.updated_modules)),
    )
    orphans = View.browse(res_id for res_id, xmlid in cr.fetchall() if xmlid not in loaded)
    # Like _process_end, keep a view whose _inherits child (a website.page) was loaded.
    for model in View._inherits_children:
        Child = View.env[model]
        if Child._abstract or not orphans:
            continue
        children = Child.with_context(active_test=False).search([(Child._inherits[View._name], "in", orphans.ids)])
        for child, xmlids in children._get_external_ids().items():
            if loaded.intersection(xmlids):
                orphans -= Child.browse(child)[Child._inherits[View._name]]
    return orphans
