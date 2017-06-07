# -*- coding: utf-8 -*-
from openupgradelib import openupgrade
from openerp.addons.base import apriori
# from . import apriori


def remove_views(cr):
    # borramos todos los external ids que apuntan a vistas no qweb
    # por si alguno tiene no actualizable y entocnes no se recrea al borrar
    # vistas en proximo paso
    openupgrade.logged_query(cr, """
        DELETE FROM ir_model_data d
        USING ir_ui_view iv WHERE d.res_id = iv.id
        AND d.model = 'ir.ui.view' and iv.type != 'qweb'
    """)

    # borramos vistas no qweb para resolver multiples inconvenientes
    openupgrade.logged_query(cr, """
        DELETE FROM ir_ui_view where type != 'qweb'
    """)


@openupgrade.migrate()
def migrate(cr, version):
    # TODO re enable if needed or delete it
    remove_views(cr)

    # por error relacionado con esto:
    # https://git.framasoft.org/framasoft/OCB/commit/31ff6c68f4b49d5c12e2487d369a338c51f8997b?view=parallel
    openupgrade.logged_query(cr, """
        DELETE FROM ir_model_data
        WHERE name = 'project_time_mode_id_duplicate_xmlid'
    """)

    # fir por l10n_ar_state desinstalado y errores en datos
    openupgrade.logged_query(cr, """
        UPDATE ir_model_data set noupdate=True WHERE
        model = 'res.country.state' and module = 'l10n_ar_states'
        """)

    # fix that afip should be no updatable
    openupgrade.logged_query(cr, """
        UPDATE ir_model_data set noupdate=True WHERE
        module = 'l10n_ar_invoice' and name = 'partner_afip'
        """)

    # from openerp.modules.registry import RegistryManager
    # from openerp import SUPERUSER_ID
    # pool = RegistryManager.get(cr.dbname)
    # ir_module_module = pool['ir.module.module']
    # domain = [('name', '=', 'stock_usability'),
    #           ('state', 'in', ('installed', 'to install', 'to upgrade'))]
    # ids = ir_module_module.search(cr, SUPERUSER_ID, domain)
    # ir_module_module.module_uninstall(cr, SUPERUSER_ID, ids)
    # ir_module_module.unlink(cr, SUPERUSER_ID, ids)

    openupgrade.update_module_names(
        cr, apriori.renamed_modules.iteritems()
    )
