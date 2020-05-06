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

    # Desinstalar modulos depreciados v11, por alguna razon por mas que el upgrade los saca puede ser que quede alguno,
    # no pudimos encontrar el problema
    # TODO si funciona podemos borrar upgrade line
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(1, dir_path)
    import dynamic_data
    to_remove = dynamic_data.to_remove
    to_uninstall = env['ir.module.module'].search(
        [('name', 'in', to_remove), ('state', 'in', ['installed', 'to upgrade'])])
    if to_uninstall:
        # TODO tal vez falte cancelar actualizacion de los to upgrade primero
        to_uninstall.button_immediate_uninstall()

    env['ir.module.module'].search([('name', 'in', to_remove), ('state', '=', 'to install')]).button_install_cancel()
    to_unlink = env['ir.module.module'].search([('name', 'in', to_remove), ('state', 'in', ['uninstalled', 'uninstallable', 'to install'])])
    to_unlink.unlink()

    # TODO REVISAR Y ACTIVAR
    # no forzamos actualizacion de plantilla de facturas y ventas porque son pocas y podemos hacerlo a mano (además nos desconfigura el reporte por defecto de Aeroo)
    # openupgrade.load_data(env.cr, 'account', 'data/mail_template_data.xml')
    # openupgrade.load_data(env.cr, 'account_document', 'data/mail_template_invoice.xml')
    # openupgrade.load_data(env.cr, 'sale', 'data/mail_data.xml')

    # recargamos traducciones (por ahora no lo hacemos, si llegamos a ver que suma y es necesario probamos activarlo)
    # env['base.language.install'].create({'lang': 'es_AR', 'overwrite': True}).lang_install()
