from openupgradelib import openupgrade
import os
import sys


@openupgrade.migrate()
def migrate(env, version):

    pass
    # load data que se requiere al final de todo, por ej:
    # if env['ir.module.module'].search([('name', '=', 'mis_builder_cash_flow'), ('state', '=', 'installed')]):
    #     for filename in ['data/mis_report.xml', 'data/mis_report_instance.xml', 'data/mis_report_style.xml']:
    #         openupgrade.load_data(env.cr, 'mis_builder_cash_flow', filename)
