from openupgradelib import openupgrade
import os
import sys


@openupgrade.migrate()
def migrate(env, version):
    # lo hacemos con try porque en pocos casos nos dio error y no queremos bloquear upgrade por esto
    try:
        openupgrade.disable_invalid_filters(env)
    except:
        pass
    # env.cr.execute(
    #     "UPDATE ir_module_module SET latest_version = '13.0.1.3' WHERE name = 'base'")

    # migracion de cash flow
    if env['ir.module.module'].search([('name', '=', 'mis_builder_cash_flow'), ('state', '=', 'installed')]):
        for filename in ['data/mis_report.xml', 'data/mis_report_instance.xml', 'data/mis_report_style.xml']:
            openupgrade.load_data(env.cr, 'mis_builder_cash_flow', filename)

    # TODO REVISAR Y ACTIVAR
    # no forzamos actualizacion de plantilla de facturas y ventas porque son pocas y podemos hacerlo a mano (además nos desconfigura el reporte por defecto de Aeroo)
    # openupgrade.load_data(env.cr, 'account', 'data/mail_template_data.xml')
    # openupgrade.load_data(env.cr, 'account_document', 'data/mail_template_invoice.xml')
    # openupgrade.load_data(env.cr, 'sale', 'data/mail_data.xml')

    # recargamos traducciones (por ahora no lo hacemos, si llegamos a ver que suma y es necesario probamos activarlo)
    # env['base.language.install'].create({'lang': 'es_AR', 'overwrite': True}).lang_install()
