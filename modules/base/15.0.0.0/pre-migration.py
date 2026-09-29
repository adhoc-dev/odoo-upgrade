# mas info sobre openupgradelib aca: https://github.com/OCA/openupgradelib/tree/master/openupgradelib
# IMPORTANTE: en realidad lo unico que estamos utilizando de esto es el patch de check views.
# TODO ver si limpiamos y/o lo movemos a otro lugar. Todo el resto lo estamos haciendo en upgrade lines de adhoc
from openupgradelib import openupgrade, openupgrade_merge_records
from odoo.addons.base.models.ir_ui_view import View
from odoo.release import major_version
import os
import sys
import logging
_logger = logging.getLogger(__name__)
# from . import dynamic_data


_original_check_xml = View._check_xml


def _check_xml(self):
    """ Patch check_xml to avoid any error when loading views, we check them later """
    try:
        _original_check_xml
    except Exception as e:
        _logger.warning('Invalid view definition. This is what we get:\n%s', e)


View._check_xml = _check_xml


@openupgrade.migrate()
def migrate(env, version):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    sys.path.insert(1, dir_path)
    import dynamic_data
    cr = env.cr

    renamed_modules = dynamic_data.renamed_modules
    merged_modules = dynamic_data.merged_modules
    xmlid_renames = dynamic_data.xmlid_renames

    openupgrade.update_module_names(cr, renamed_modules.items())
    openupgrade.update_module_names(cr, merged_modules.items(), merge_modules=True)
    openupgrade.rename_xmlids(env.cr, xmlid_renames)

    # esto ahora lo estamos haciendo en Modules renames/merge and xmlid renames xx to yy
    # # a los modulos que hicimos merge y que no estaba instalados quedan con version vacia pero necesitamos que tengan
    # # version para que se corran los scripts (caso l10n_ar, l10n_latam_invoice_document, etc)
    # openupgrade.logged_query(cr, """
    #     UPDATE ir_module_module
    #     SET latest_version = '%s.0.0.0'
    #     WHERE latest_version is null and state = 'installed'
    #     """ % major_version)

# CUALQUIER Monkey patch necesario lo podemos hacer acá, por ej:
# fix cuando instalamos helpdesk sobre issues migrados al querer obtener un default team, sacamos el default
# from odoo.addons.helpdesk.models.helpdesk_ticket import HelpdeskTicket
# from odoo import fields
# HelpdeskTicket.team_id = fields.Many2one('helpdesk.team', string='Helpdesk Team', index=True)
