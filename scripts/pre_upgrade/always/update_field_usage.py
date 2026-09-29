import logging
import os

import requests

from odoo.release import major_version
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Catálogo de cambios entre versiones que mantiene el equipo en adhoc.adhoc.inc
# (el dominio .ar redirige ahí).
CHANGES_URL = "https://adhoc.adhoc.ar/version_changes/%s/%s"
REQUEST_TIMEOUT = 60


def _get_versions(version):
    """Origen y destino del salto que se está corriendo.

    Las declara el runner del pase (`odoo_obaupgrade.py` de
    `saas_provider_upgrade`) y llegan en el entorno del proceso. Sin ellas —una
    corrida local, runbot— se reconstruyen: el destino es el Odoo que corre el
    `-u` y el origen, la versión de `base` instalada en la base.
    """
    from_version = os.environ.get("MYSCRIPT_FROM_VERSION") or "%s.0" % version.split(".")[0]
    to_version = os.environ.get("MYSCRIPT_TO_VERSION") or major_version
    return from_version, to_version


def _get_version_changes(from_version, to_version):
    url = CHANGES_URL % (from_version.replace(".", ""), to_version.replace(".", ""))
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _get_field_renames(changes, to_version):
    renames = []
    for change in changes.values():
        if (
            change.get("major_version_id") != to_version
            or change.get("change_type") != "rename"
            or change.get("model_type") != "field"
        ):
            continue
        model, old_name, new_name = change.get("model"), change.get("old_name"), change.get("new_name")
        # El catálogo se carga a mano y tiene destinos que no son un campo: dos
        # nombres separados por coma, o un camino con punto.
        if not model or not isinstance(old_name, str) or not isinstance(new_name, str) or not new_name.isidentifier():
            _logger.warning("Skipping invalid field rename: %s %s -> %s", model, old_name, new_name)
            continue
        renames.append((model, old_name, new_name))
    return renames


def migrate(cr, version):
    """Aplica los renombres de campo que el catálogo declara para este salto.

    Migrado desde la upgrade line 1118 ("UPGRADE FIELDS (Upgrade-util)"), que
    hacía lo mismo por RPC en un pod de Odoo Shell después del `-u all`.

    `update_field_usage` no toca la columna —de eso se encarga el módulo que
    renombró el campo— sino las referencias que quedaron en datos del cliente:
    filtros, exportaciones, acciones de servidor, alias, dominios y related.

    Corre antes del `-u` y no después, como corría la upgrade line, porque un
    related roto lo levanta la carga de los módulos: arreglarlo acá le llega a
    tiempo. Las vistas no entran en el juego, `update_field_usage` no las toca.
    """
    _logger.info("Running 'update_field_usage.py' script for version %s", version)

    try:
        from_version, to_version = _get_versions(version)
        changes = _get_version_changes(from_version, to_version)
    except Exception:
        # Sin catálogo no se aplica ningún renombre, pero la base actualizada
        # funciona igual: no cortamos el upgrade por esto.
        _logger.exception("Could not read the version changes catalog; no field rename was applied")
        return

    renames = _get_field_renames(changes, to_version)
    for model, old_name, new_name in renames:
        _logger.info("Updating field usage on %s: %s -> %s", model, old_name, new_name)
        util.update_field_usage(cr, model, old_name, new_name)

    _logger.info("Applied %s field renames from %s to %s", len(renames), from_version, to_version)
