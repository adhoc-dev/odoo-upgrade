# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # lo hacemos con try porque en pocos casos nos dio error y no queremos
    # bloquear upgrade por esto
    try:
        openupgrade.disable_invalid_filters(env)
    except:
        pass
    env.cr.execute(
        "UPDATE ir_module_module SET latest_version = '11.0.1.3' "
        "WHERE name = 'base'")
    # recargamos traducciones
    env['base.language.install'].create(
        {'lang': 'es_AR', 'overwrite': True}).lang_install()
