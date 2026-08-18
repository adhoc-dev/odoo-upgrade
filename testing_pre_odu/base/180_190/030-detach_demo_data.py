import csv
import logging
import os
from xml.etree import ElementTree

from odoo.modules.module import get_manifest, get_module_path

_logger = logging.getLogger(__name__)

# Odoo pidio explicitamente que no le mandemos bases con demo (respuesta de Alvaro Fuentes del
# 07/08): el upgrade de modulos con demo no tiene soporte oficial. Y se notaba: fallaba la carga
# de demo en 8 modulos. La causa es que los archivos demo se cargan con noupdate=True y en un
# upgrade el modo es `update`, combinacion con la que convert.py:_tag_function saltea todos los
# <function>; los xmlids que 19 registra por esa via nunca existen.
#
# En vez de perseguir xmlids de a uno, sacamos la base de modo demo: borramos el XMLID (nunca el
# registro) y apagamos el flag. Los registros quedan sin dueno, comportandose como data de
# cliente. Con el flag apagado loading.py ni siquiera llama a load_demo (`if package.demo:`).
# Es el punto 1 de nmr en la tarea 69634. Medido en el build 102281: cero cargas de demo, cero
# ForeignKeyViolation en _process_end y el parche keep_demo_data del step 24 no tuvo que actuar.
#
# Va ultimo a proposito: despues de borrar xmlids la cache de _xmlid_lookup queda desactualizada,
# asi que ningun otro script deberia resolver refs en este mismo environment.
#
# Los errores de parseo NO se silencian: un detach parcial es peor que ninguno. Dejaria xmlids de
# demo sueltos con el flag ya apagado, que es la combinacion que hace que _process_end los purgue
# como huerfanos y tiren ForeignKeyViolation.

DEMO_KEYS = ("demo", "demo_xml")
DATA_KEYS = ("data", "init_xml", "update_xml")

# Red de seguridad: en el build 102274 una version anterior borro base.group_user y el
# pre-only-one-user-type-group.py de Odoo murio insertando un gid NULL en res_groups_users_rel.
SACRED = {
    ("base", "group_user"),
    ("base", "group_portal"),
    ("base", "main_company"),
    ("base", "user_admin"),
}


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


def migrate(env):
    """Saca la base de modo demo: borra los xmlids de demo y apaga el flag."""
    modules = env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")

    declared_demo = set()
    declared_data = set()
    with_demo = missing_path = 0
    for module in sorted(modules):
        path = get_module_path(module, display_warning=False)
        if not path:
            missing_path += 1
            continue
        manifest = get_manifest(module)
        demo = _declared(manifest, module, path, DEMO_KEYS)
        if demo:
            with_demo += 1
        declared_demo |= demo
        declared_data |= _declared(manifest, module, path, DATA_KEYS)

    # La resta es GLOBAL, no por modulo: el demo de un modulo puede declarar un xmlid que
    # pertenece a otro (el demo de crm declara sales_team.team_sales_department, y varios
    # declaran registros de base). Restando dentro del mismo modulo se borran xmlids que su
    # dueno declara como data.
    to_delete = declared_demo - declared_data
    if to_delete & SACRED:
        raise RuntimeError("El calculo de xmlids de demo incluye data esencial: %s"
                           % sorted(to_delete & SACRED))

    _logger.info(
        "Detaching demo data: %s installed module(s), %s with demo files, %s xmlid(s) declared, "
        "%s without code on disk",
        len(modules), with_demo, len(to_delete), missing_path,
    )

    if to_delete:
        # Diagnostico, NO cambia comportamiento: cuantos de estos xmlids tocaria de verdad el
        # purgado de huerfanos. `_process_end` (odoo/addons/base/models/ir_model.py) filtra
        # `COALESCE(noupdate, false) != true`, y la demo se carga con noupdate=True
        # (odoo/modules/loading.py: `noupdate=kind == 'demo'`). O sea que si el grueso cae en
        # noupdate=True, borrarlos no es lo que evita la ForeignKeyViolation que motivo este
        # script, y alcanzaria con un detach selectivo: apagar el flag y borrar solo los
        # noupdate=False. Eso dejaria la data demo referenciable por xmlid, que es la premisa
        # de los tests declarativos de odoo-upgrade (ADR 0007 de actua-20: la fuente primaria
        # de casos es la data de prueba que ya trae la base).
        # Medicion pedida desde actua-20 antes de decidir si el borrado completo sigue.
        env.cr.execute(
            "SELECT COALESCE(noupdate, false), count(*) FROM ir_model_data "
            "WHERE (module, name) IN %s GROUP BY 1",
            (tuple(to_delete),),
        )
        split = dict(env.cr.fetchall())
        _logger.info(
            "noupdate split of the demo xmlids present in the database: True=%s (protected from "
            "_process_end), False=%s (the only ones the orphan purge would remove)",
            split.get(True, 0), split.get(False, 0),
        )
        env.cr.execute(
            "SELECT model, count(*) FROM ir_model_data "
            "WHERE (module, name) IN %s AND COALESCE(noupdate, false) = false "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 15",
            (tuple(to_delete),),
        )
        by_model = env.cr.fetchall()
        if by_model:
            _logger.info(
                "Models behind the noupdate=False xmlids: %s",
                ", ".join("%s=%s" % (model, count) for model, count in by_model),
            )

        env.cr.execute("DELETE FROM ir_model_data WHERE (module, name) IN %s", (tuple(to_delete),))
        _logger.info("Deleted %s demo xmlid(s) present in the database", env.cr.rowcount)

    env.cr.execute("UPDATE ir_module_module SET demo = false WHERE demo")
    _logger.info("Turned the demo flag off on %s module(s)", env.cr.rowcount)
