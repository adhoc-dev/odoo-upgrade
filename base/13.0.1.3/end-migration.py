from openupgradelib import openupgrade
import os
import sys


@openupgrade.migrate()
def migrate(env, version):
    # lo hacemos en post script porque por mas que le ponemos un try si da error se nos rompe el upgrade
    # # lo hacemos con try porque en pocos casos nos dio error y no queremos bloquear upgrade por esto
    # try:
    #     openupgrade.disable_invalid_filters(env)
    # except:
    #     pass

    # migracion de cash flow
    if env['ir.module.module'].search([('name', '=', 'mis_builder_cash_flow'), ('state', '=', 'installed')]):
        for filename in ['data/mis_report.xml', 'data/mis_report_instance.xml', 'data/mis_report_style.xml']:
            openupgrade.load_data(env.cr, 'mis_builder_cash_flow', filename)

    # Lo hacemos en post script porque si hay un error en alguna traduccion se rompe todo el upgrade
    # # recargamos traducciones (por ahora no lo hacemos, si llegamos a ver que suma y es necesario probamos activarlo)
    # env['base.language.install'].create({'lang': 'es_AR', 'overwrite': True}).lang_install()
