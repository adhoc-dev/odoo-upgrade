from openupgradelib import openupgrade
import os
from odoo import tools


@openupgrade.migrate()
def migrate(env, version):

    def load_csv(module_name, filename):
        pathname = os.path.join(module_name, filename)
        fp = tools.file_open(pathname, 'rb')
        tools.convert_csv_import(env.cr, module_name, pathname, fp.read(), None, 'init', True)
        fp.close()
    load_csv('l10n_ar', 'data/res.country.csv')
    load_csv('l10n_ar', 'data/res.currency.csv')

    # forzar actualizacion de la data de los tax groups y otras data
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/account_tax_group.xml')
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/uom_uom_data.xml')
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_service_start = ai.afip_service_start
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_service_start is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_service_end = ai.afip_service_end
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_service_end is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_currency_rate = ai.currency_rate
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.currency_rate is not null
        """)
