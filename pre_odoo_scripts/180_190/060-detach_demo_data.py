import csv
import logging
import os
from xml.etree import ElementTree

from odoo.modules.module import get_manifest, get_module_path

_logger = logging.getLogger(__name__)

# OJO: esto es para la base demo, no para clientes. Vive aca y no en upgrade-prepare-demo solo
# porque ese repo esta tomado por otro trabajo. Una base de cliente no tiene xmlids de demo, asi
# que seria no-op, pero es el mas destructivo de los scripts de demo: sacarlo de este repo antes
# de que el step del provider llegue a produccion.
#
# Odoo pidio explicitamente que no le mandemos bases con demo (respuesta de Alvaro Fuentes del
# 07/08). Y se nota: en el build 102000 fallan la carga de demo 8 modulos. La causa es que los
# archivos demo se cargan con noupdate=True y en un upgrade el modo es `update`, combinacion con
# la que convert.py:_tag_function saltea todos los <function>; los xmlids que 19 registra por esa
# via nunca existen.
#
# En vez de perseguir xmlids de a uno, sacamos la base de modo demo: borramos el XMLID (nunca el
# registro) y apagamos el flag. Los registros quedan sin dueno, comportandose como data de
# cliente. Con el flag apagado loading.py ni siquiera llama a load_demo (`if package.demo:`), asi
# que los 8 fallos se van juntos. Es el punto 1 de nmr en la tarea 69634.
#
# Los errores de parseo NO se silencian a proposito: un detach parcial es peor que ninguno.
# Dejaria xmlids de demo sueltos con el flag ya apagado, que es justo la combinacion que hace que
# _process_end los purgue como huerfanos y tiren ForeignKeyViolation. Si un archivo no parsea,
# preferimos que falle el step y la base no se envie.

DEMO_KEYS = ("demo", "demo_xml")
DATA_KEYS = ("data", "init_xml", "update_xml")


def _xmlids(path, module):
    """XMLIDs declarados en un archivo de data, como pares (modulo, nombre)."""
    found = set()
    if path.endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                xmlid = (row.get("id") or "").strip()
                if xmlid:
                    found.add(xmlid)
    elif path.endswith(".xml"):
        # Cualquier elemento con atributo `id` declara un registro: record, template, menuitem,
        # report, act_window. Los <field> no lo llevan, asi que no hay falsos positivos.
        for element in ElementTree.parse(path).getroot().iter():
            xmlid = element.get("id")
            if xmlid:
                found.add(xmlid)
    return {tuple(x.split(".", 1)) if "." in x else (module, x) for x in found}


def _declared(module, path, keys):
    declared = set()
    for key in keys:
        for filename in get_manifest(module).get(key) or ():
            full_path = os.path.join(path, filename)
            if os.path.exists(full_path):
                declared |= _xmlids(full_path, module)
    return declared


def migrate(cr, version):
    """Saca la base de modo demo: borra los xmlids de demo y apaga el flag."""
    cr.execute("SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name")
    modules = [name for (name,) in cr.fetchall()]

    to_delete = set()
    with_demo = missing_path = 0
    for module in modules:
        path = get_module_path(module, display_warning=False)
        if not path:
            missing_path += 1
            continue
        demo = _declared(module, path, DEMO_KEYS)
        if not demo:
            continue
        with_demo += 1
        # Si el xmlid tambien se declara en un archivo no-demo, el registro es legitimo y el demo
        # solo lo extiende: borrarlo romperia el de verdad.
        to_delete |= demo - _declared(module, path, DATA_KEYS)

    _logger.info(
        "Detaching demo data: %s installed module(s), %s with demo files, %s xmlid(s) declared, "
        "%s without code on disk",
        len(modules), with_demo, len(to_delete), missing_path,
    )

    if to_delete:
        cr.execute("DELETE FROM ir_model_data WHERE (module, name) IN %s", (tuple(to_delete),))
        _logger.info("Deleted %s demo xmlid(s) present in the database", cr.rowcount)

    cr.execute("UPDATE ir_module_module SET demo = false WHERE demo")
    _logger.info("Turned the demo flag off on %s module(s)", cr.rowcount)
