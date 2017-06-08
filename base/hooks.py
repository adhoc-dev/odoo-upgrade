# -*- coding: utf-8 -*-
from openerp.modules import loading
from openerp.modules.loading import load_module_graph
import logging
_logger = logging.getLogger(__name__)


def add_module_dependencies(cr, module_list):
    """
    Robamos este metodo de openupgrade y sacamos la parte que extiende al
    config
    """
    if not module_list:
        return module_list

    modules_in = list(module_list)
    module_list = list(set(module_list))

    dependencies = module_list
    while dependencies:
        cr.execute("""
            SELECT DISTINCT dep.name
            FROM
                ir_module_module,
                ir_module_module_dependency dep
            WHERE
                module_id = ir_module_module.id
                AND ir_module_module.name in %s
                AND dep.name not in %s
            """, (tuple(dependencies), tuple(module_list),))

        dependencies = [x[0] for x in cr.fetchall()]
        module_list += dependencies

    # Select auto_install modules of which all dependencies
    # are fulfilled based on the modules we know are to be
    # installed
    cr.execute("""
        SELECT name from ir_module_module WHERE state IN %s
        """, (('installed', 'to install', 'to upgrade'),))
    modules = list(set(module_list + [row[0] for row in cr.fetchall()]))
    cr.execute("""
        SELECT name from ir_module_module m
        WHERE auto_install IS TRUE
            AND state = 'uninstalled'
            AND NOT EXISTS(
                SELECT id FROM ir_module_module_dependency d
                WHERE d.module_id = m.id
                AND name NOT IN %s)
         """, (tuple(modules),))
    # TODO ver si queremos esto aca, en realidad los auto instalamos
    # despues con adhoc modules
    # auto_modules = [
    #     row[0] for row in cr.fetchall()
    #     if get_module_path(row[0])
    # ]
    # if auto_modules:
    #     logger.info(
    #         "Selecting autoinstallable modules %s", ','.join(auto_modules))
    #     module_list += auto_modules

    # Set proper state for new dependencies so that any init scripts are run
    cr.execute("""
        UPDATE ir_module_module SET state = 'to install'
        WHERE name IN %s AND name NOT IN %s AND state = 'uninstalled'
        """, (tuple(module_list), tuple(modules_in)))
    return module_list


def load_marked_modules(
        cr, graph, states, force, progressdict, report, loaded_modules,
        perform_checks):
    """Usamos un metodo similar al de openupgrade pero sin el upg_registry"""
    print 'aaaaa'
    print 'aaaaa'
    print 'aaaaa'
    print 'aaaaa'
    print 'aaaaa'
    print 'aaaaa'
    print 'aaaaa'
    processed_modules = []
    while True:
        cr.execute(
            "SELECT name from ir_module_module WHERE state IN %s",
            (tuple(states),))
        module_list = [name for (name,) in cr.fetchall() if name not in graph]
        module_list = add_module_dependencies(cr, module_list)
        if not module_list:
            break
        graph.add_modules(cr, module_list, force)
        _logger.debug('Updating graph with %d more modules', len(module_list))
        loaded, processed = load_module_graph(
            cr, graph, progressdict, report=report,
            skip_modules=loaded_modules, perform_checks=perform_checks)
        processed_modules.extend(processed)
        loaded_modules.extend(loaded)
        if not processed:
            break
    return processed_modules


loading.load_marked_modules = load_marked_modules
