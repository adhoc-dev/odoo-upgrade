"""Uninstall the modules with no code in the target version.

The upgrade line "Módulos no disponibles" (saas.upgrade.line 2291) as a migration script:
same classification and same messages, with the module catalog taken from the provider
endpoint ``/module_states/<version>`` instead of its ORM, and the request taken from the
context the runner leaves in the database.

A module still ``to upgrade`` or ``to install`` when the load loop ends has no code in this
version. Against the catalog it is discarded (in the target or in a version the series went
through), migrating, or unknown: the first two are removed, the migrating ones are told to
the customer, the unknown ones are left for the PO to decide.

In ``base/0.0.0`` so it runs on every jump, last among the end scripts. Only with a request
context and only on the last request of a series, as the upgrade line did with
``execution_position``; a ``-u`` without the runner does nothing.
"""

import logging

import requests

from odoo import release
from odoo.upgrade import util
from odoo.upgrade.oba import add_customer_note, log_message, request_context

_logger = logging.getLogger(__name__)

CATALOG_URL = "https://adhoc.adhoc.inc/module_states/%s"
REQUEST_TIMEOUT = 120
MIGRATING_STATE_ID = 2  # adhoc.module.state "Migrando"
# Written by hand on the upgrade line that renders the note: one spelling.
CUSTOMER_NOTE_SLUG = "modulos-no-disponibles"


def migrate(cr, version):
    context = request_context(cr)
    if not context:
        _logger.info("No upgrade request context: nothing to do outside a provider run")
        return
    if not context.get("is_last_in_series", True):
        _logger.info("Not the last request of the series: the modules are handled there")
        return
    run(cr, context)


def run(cr, context, to_version=None, catalog=None, remove=util.remove_module):
    """The upgrade line, from the classification to the messages.

    :param context: the request context, with ``from_version`` and the position in the series
    :param to_version: the target version; the running Odoo by default
    :param catalog: callable(version) -> catalog or None; the endpoint by default
    :param remove: callable(cr, module) that removes one module
    """
    catalog = catalog or module_states
    to_version = to_version or release.serie
    target = catalog(to_version)
    if target is None:
        raise Exception("No module catalog for version %s at %s" % (to_version, CATALOG_URL % to_version))

    not_available = not_available_modules(cr)
    versions = previous_versions(
        to_version, context.get("from_version") or to_version, context.get("is_first_in_series", True)
    )
    to_remove, migrating, pending_install, unknown = classify(not_available, target, versions, catalog)

    if pending_install:
        log_message(
            cr,
            "Módulos usables en la versión destino, pendientes de instalar por el fixdb (no se analizan): %s"
            % pending_install,
            "info",
        )

    # 1. discarded or migrating: handled cases, they can be removed
    if to_remove:
        dependents = installed_dependents(cr, to_remove)
        # deepest dependents first, as the uninstall would take them along
        for name in dependents[::-1] + to_remove:
            remove(cr, name)
        message = ["Módulos desinstalados: %s" % to_remove]
        if dependents:
            message.append("Dependientes desinstalados: %s" % dependents)
        log_message(cr, "\n".join(message), "info")

    # 2. not available but migrating: tell the customer
    if migrating:
        add_customer_note(cr, CUSTOMER_NOTE_SLUG, {"migrar_modules_info": migrating})

    # 3. not available and not removed: nobody decided about them yet
    if unknown:
        log_message(
            cr,
            'Estos modulos están %s "A evaluar más adelante", '
            "hay que activar tarea de actualización para que el PO evalue migrar o descartar. Para eso utilizar "
            'la acción de servidor "[AdV] Crear Tareas de Migración de Módulos" disponible sobre el mismo Log Entry'
            % unknown,
            "warning",
        )


def module_states(version):
    """Catalog of one major version by module name, or ``None`` when that version does not exist.

    Each entry carries ``state``, ``state_id``, ``state_category``, ``summary`` and
    ``discarded``: a not usable record exists for the name, whatever the entry's own state.
    """
    response = requests.get(CATALOG_URL % version, timeout=REQUEST_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()["modules"]


def not_available_modules(cr):
    """Names still to upgrade or to install: their code is not in this version."""
    cr.execute("SELECT name FROM ir_module_module WHERE state IN ('to upgrade', 'to install') ORDER BY name")
    return [name for (name,) in cr.fetchall()]


def previous_versions(to_version, from_version, first_in_series):
    """Versions to look for discarded modules in, newest first.

    The upgrade line walked the versions strictly between the first database of the series
    and the target. The context carries the origin of this request, not of the series, so
    the walk goes down to this request's origin unless it is also the first one: the same
    versions on series of one and two jumps, which are the ones that exist.
    """
    target = int(to_version.split(".")[0])
    floor = target if first_in_series else int(from_version.split(".")[0])
    return ["%s.0" % major for major in range(target - 1, floor - 1, -1)]


def classify(not_available, target, versions, catalog):
    """Split the names with no code by what the catalog says of them.

    :return: ``(to_remove, migrating, pending_install, unknown)``; ``migrating`` as
        ``(name, summary)`` pairs for the customer note, the rest as sorted names
    """
    usables = {name for name, info in target.items() if info["state_category"] == "usable"}
    # discarded in one repo and not usable in another one
    discarded = {name for name, info in target.items() if info["discarded"] and name not in usables}
    migrating = {
        name
        for name, info in target.items()
        if info["state_category"] == "not_available" and info["state_id"] == MIGRATING_STATE_ID
    }

    # Usable in the target but still to install: a previous script marked it and the next
    # load installs it. Not a missing module, keep it out of the analysis.
    pending_install = sorted(set(not_available) & usables)
    not_available = [name for name in not_available if name not in usables]

    # A module discarded in N-2 has no record in N-1 nor in N: walk back for the names the
    # target does not know, until every one is found. A version that does not exist is skipped.
    pending = {name for name in not_available if name not in target}
    for version in versions:
        if not pending:
            break
        states = catalog(version)
        if states:
            found = {name for name in pending if states.get(name, {}).get("discarded")}
            discarded |= found
            pending -= found

    to_remove = sorted(set(not_available) & (discarded | migrating))
    migrating_info = [(name, target[name]["summary"]) for name in sorted(set(not_available) & migrating)]
    unknown = sorted(set(not_available) - set(to_remove))
    return to_remove, migrating_info, pending_install, unknown


def installed_dependents(cr, names):
    """Modules installed on top of ``names``, direct ones first, as the uninstall takes them along."""
    dependents = []
    frontier = list(names)
    while frontier:
        cr.execute(
            """
            SELECT DISTINCT m.name
              FROM ir_module_module m
              JOIN ir_module_module_dependency d ON d.module_id = m.id
             WHERE d.name IN %s
               AND m.state NOT IN ('uninstalled', 'uninstallable')
               AND m.name NOT IN %s
            """,
            (tuple(frontier), tuple(list(names) + dependents)),
        )
        frontier = sorted(name for (name,) in cr.fetchall())
        dependents += frontier
    return dependents
