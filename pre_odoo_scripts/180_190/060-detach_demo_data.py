import ast
import csv
import logging
import os
from xml.etree import ElementTree

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


def _addons_roots():
    """Directorios donde buscar modulos.

    No se puede usar `odoo.modules.module`: el runner corre como python plano y ahi `odoo`
    resuelve solo al namespace de upgrade-util, sin el Odoo completo (`ModuleNotFoundError:
    No module named 'odoo.modules'`, build 102239). Los repos estan montados como hermanos del
    nuestro, asi que salimos desde la ruta de este archivo.
    """
    build_dir = os.path.abspath(__file__)
    for _ in range(4):  # .../<build>/<repo>/pre_odoo_scripts/180_190/<este archivo>
        build_dir = os.path.dirname(build_dir)

    roots = []
    for entry in sorted(os.listdir(build_dir)):
        repo = os.path.join(build_dir, entry)
        if not os.path.isdir(repo):
            continue
        roots.append(repo)
        # El core trae sus modulos en subcarpetas, no en la raiz del repo
        for sub in ("addons", os.path.join("odoo", "addons")):
            if os.path.isdir(os.path.join(repo, sub)):
                roots.append(os.path.join(repo, sub))
    return roots


def _module_path(module, roots):
    for root in roots:
        if os.path.exists(os.path.join(root, module, "__manifest__.py")):
            return os.path.join(root, module)
    return None


def _manifest(path):
    # Mismo parseo que usa Odoo en modules/module.py: ast.literal_eval del archivo entero.
    with open(os.path.join(path, "__manifest__.py"), encoding="utf-8") as handle:
        return ast.literal_eval(handle.read())


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


def _declared(manifest, module, path, keys):
    declared = set()
    for key in keys:
        for filename in manifest.get(key) or ():
            full_path = os.path.join(path, filename)
            if os.path.exists(full_path):
                declared |= _xmlids(full_path, module)
    return declared


def migrate(cr, version):
    """Saca la base de modo demo: borra los xmlids de demo y apaga el flag."""
    cr.execute("SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name")
    modules = [name for (name,) in cr.fetchall()]

    roots = _addons_roots()
    # Chequeo de cordura: si no encontramos `base` es que el layout no es el esperado y estariamos
    # por hacer un detach parcial, que es peor que ninguno.
    if not _module_path("base", roots):
        raise RuntimeError("No se encontro el modulo `base` en %s carpeta(s) de addons" % len(roots))

    to_delete = set()
    with_demo = missing_path = 0
    for module in modules:
        path = _module_path(module, roots)
        if not path:
            missing_path += 1
            continue
        manifest = _manifest(path)
        demo = _declared(manifest, module, path, DEMO_KEYS)
        if not demo:
            continue
        with_demo += 1
        # Si el xmlid tambien se declara en un archivo no-demo, el registro es legitimo y el demo
        # solo lo extiende: borrarlo romperia el de verdad.
        to_delete |= demo - _declared(manifest, module, path, DATA_KEYS)

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
