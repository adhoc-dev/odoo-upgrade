from openupgradelib import openupgrade, openupgrade_merge_records
from odoo.addons.base import dynamic_data


@openupgrade.migrate()
def migrate(env, version):
    cr = env.cr

    renamed_modules = dynamic_data.renamed_modules
    merged_modules = dynamic_data.merged_modules
    to_remove = dynamic_data.to_remove

    # TODO por ahora no lo hacemos aca ya que tampoco viene siendo necesario
    # pero lo dejamos planteado por si llega a venir bien, en ese caso
    # habria que adaptar saas_upgrade para que mande el to_remove
    # we set to remove from here and not after install because now we are
    # setting modules as "installed" (instead of on to upgrade) when we
    # restore the upgraded database, and later, when we run -u all, when odoo
    # calls button_upgrade method, it can raise to error because of deprecated
    # modules without dependencies, so we set them to move
    # TODO we are not unintalling downstream_dependencies

    if to_remove:
        # a todos los que querramos borrar los ponemos a desinstalar y tambien
        # le sacamos el auto_install porque si no se terminan instalando luego
        openupgrade.logged_query(cr, """
            UPDATE ir_module_module
            SET state = 'to remove', auto_install = false
            WHERE name in %s AND state in ('installed', 'to upgrade')
            """, (tuple(to_remove),))

    openupgrade.update_module_names(cr, renamed_modules.items())
    openupgrade.update_module_names(cr, merged_modules.items(), merge_modules=True)

    # TODO implementar?
    # xmlid_renames = [
    #     ('auth_signup.default_template_user', 'base.template_portal_user_id'),
    # ]
    # openupgrade.rename_xmlids(env.cr, xmlid_renames)

    # fix_aeroo_reports(cr)


# def fix_aeroo_reports(cr):
#     openupgrade.logged_query(cr, """
#         UPDATE ir_act_report_xml SET parser_state = 'default',
#             parser_loc = false
#     """)


# fix cuando instalamos helpdesk sobre issues migrados al querer obtener un
# default team, sacamos el default
from odoo.addons.helpdesk.models.helpdesk_ticket import HelpdeskTicket
from odoo import fields
HelpdeskTicket.team_id = fields.Many2one(
    'helpdesk.team', string='Helpdesk Team', index=True)
