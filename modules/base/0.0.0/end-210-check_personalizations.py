"""Check the customer's personalizations in the new database and leave what the customer note shows.

Personalizations by module (``personalizations`` or ``p13n`` anywhere in the name):

- migrated, installed in the new database: the note tells the customer to check them.
- not migrated (no code in this version, still ``to upgrade`` or ``to install`` when the
  load loop ends): the module is removed, a warning with a fixed text goes to the request,
  and the request stops, unless the ticket parameter ``ignore_personalizations_check`` is
  set. The customer note validation looks for that text, so it must not change.

Personalizations by interface: read from the "Mi base" dashboard (``saas_client.dashboard``)
when its module is loaded; if not, only the custom views count, as the upgrade line did when
the dashboard could not be read. Each custom view is written back to itself to find the ones
that fail in this version: when the customer maintains their personalizations
(``saas_client.own_personalizations_agreement``) those are archived and counted; when Adhoc
does, they go to the request as a warning.

The values the customer note renders go through ``add_customer_note``; the note itself is a
Test & C. Notes upgrade line with no script.

Only on the last request of a series. In ``modules/base/0.0.0`` so it runs on every jump,
after the modules are loaded, and before ``end-900``, which would leave a personalization
module it does not know as unknown.
"""

import logging

from odoo import release
from odoo.upgrade import util
from oba import add_customer_note, log_message, request_context, set_breaks, should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 2290.
FIRST_TARGET_VERSION = 20
# Matched by the customer note validation script: keep it literal.
MISSING_MODULE_WARNING = "No podemos avanzar hasta que este migrado el modulo perso e instalado."
MISSING_MODULE_BREAKS = "No podemos avanzar hasta que el módulo de personalizaciones esté migrado e instalado."
# As the upgrade line searched them: the ORM ilike matches anywhere in the name.
PERSONALIZATION_PATTERNS = ("%personalizations%", "%p13n%")


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, position="last"):
        return

    module_migrated = _check_modules(cr)
    interface_adhoc, interface_client, disabled_views = _check_interface(cr)

    add_customer_note(
        cr,
        {
            "personalizations_any": bool(interface_adhoc or interface_client or module_migrated),
            "personalizations_interface_adhoc": interface_adhoc,
            "personalizations_interface_client": interface_client,
            "personalizations_disabled_views": disabled_views,
            "personalizations_module_migrated": module_migrated,
            # The docs link of the note goes to the docs of the target version.
            "personalizations_version": release.version_info[0],
        },
    )


def _check_modules(cr):
    """Whether a personalization module is migrated; the ones that are not are removed."""
    cr.execute(
        "SELECT name, state FROM ir_module_module WHERE name ILIKE %s OR name ILIKE %s ORDER BY name",
        PERSONALIZATION_PATTERNS,
    )
    modules = cr.fetchall()
    missing = [name for name, state in modules if state in ("to upgrade", "to install")]
    migrated = any(state == "installed" for _name, state in modules)
    if not missing:
        return migrated

    # end-900 does not know them: they have no version in the module catalog.
    for name in missing:
        _logger.info("Removing the personalization module %s: it has no code in this version", name)
        util.remove_module(cr, name)

    if (request_context(cr).get("parameters") or {}).get("ignore_personalizations_check"):
        _logger.info("Personalization modules not migrated %s: ignored by the ticket parameter", missing)
        return migrated
    log_message(cr, MISSING_MODULE_WARNING, "warning")
    set_breaks(cr, MISSING_MODULE_BREAKS)
    return migrated


def _check_interface(cr):
    """(Adhoc maintains them, the customer does, views archived), for the interface ones."""
    env = util.env(cr)
    has_personalizations, view_ids = _from_dashboard(env)
    if has_personalizations is None:
        has_personalizations, view_ids = _from_views(cr)
    if not has_personalizations:
        return False, False, 0

    broken = []
    for view in env["ir.ui.view"].search([("id", "in", view_ids)]):
        try:
            with cr.savepoint():
                view.write({"arch_db": view.arch_db})
        except Exception:
            broken.append(view.id)

    cr.execute("SELECT value FROM ir_config_parameter WHERE key = 'saas_client.own_personalizations_agreement'")
    row = cr.fetchone()
    if row and row[0]:
        if broken:
            cr.execute("UPDATE ir_ui_view SET active = false WHERE id = ANY(%s)", (broken,))
            _logger.info("Archived %s custom views that fail in this version: %s", len(broken), broken)
        return False, True, len(broken)
    if broken:
        log_message(cr, "Revisar vistas Personalizadas para ajustarlas %s" % broken, "warning")
    return True, False, 0


def _from_dashboard(env):
    """(has interface personalizations, their views) from "Mi base", or (None, None)."""
    if "saas_client.dashboard" not in env:
        _logger.info("No 'Mi base' dashboard in the new database: only the views count")
        return None, None
    try:
        with env.cr.savepoint():
            dashboard = env["saas_client.dashboard"].create({})
            return bool(dashboard.has_interface_personalizations), dashboard.view_ids.ids
    except Exception:
        log_message(env.cr, "No se pudo leer 'Mi base' en la new, se detecta solo por vistas.", "warning")
        return None, None


def _from_views(cr):
    """The custom views, as the upgrade line counted them without the dashboard."""
    cr.execute(
        """
        SELECT v.id
          FROM ir_ui_view v
          LEFT JOIN ir_model_data d ON d.model = 'ir.ui.view' AND d.res_id = v.id
         WHERE (d.res_id IS NULL OR d.module IN ('__export__', 'studio_customization'))
           AND v.type != 'qweb'
         ORDER BY v.id
        """
    )
    view_ids = [row[0] for row in cr.fetchall()]
    return bool(view_ids), view_ids
