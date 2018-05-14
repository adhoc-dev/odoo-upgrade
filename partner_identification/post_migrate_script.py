# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from . import obsolte_modules
from . import new_obsolete
import logging

_logger = logging.getLogger(__name__)


def run(env):
    # desinstalamos y borramos modulos depreciados
    modules = env['ir.module.module'].search([('name', 'in', obsolte_modules)])
    modules.module_uninstall()
    modules.unlink()

    # volvemos a poner base en version que corresponde
    env.cr.execute("""
        UPDATE ir_module_module SET latest_version = '9.0.1.3'
        WHERE name = 'base'""")

    # esto no recuerdo que era
    env.cr.execute("""
        UPDATE ir_act_window SET auto_search = true WHERE id in
            (SELECT res_id from ir_model_data WHERE name in
                ('product_template_action', 'product_normal_action_sell',
                'action_partner_form') and module in ('base', 'product'))""")

    # re cargamos idioma español ar
    wizard = env['base.language.install'].create(
        {'lang': 'es_AR', 'overwrite': True})
    wizard.with_context({'active_ids': [wizard.id]}).lang_install()

    # nuevo para limpiar mas modulos
    env['ir.module.module'].search([
        ('name', 'in', new_obsolete),
        ('state', 'in', ['uninstalled', 'uninstallable'])]).unlink()
