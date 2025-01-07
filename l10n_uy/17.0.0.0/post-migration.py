from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Running post-migrate script for l10n_uy')
    env = api.Environment(cr, SUPERUSER_ID, {})
    #Impuestos
    query= f"""
            SELECT tax.id
            FROM account_tax_group AS tax_group
            INNER JOIN account_tax AS tax
            ON tax_group.id = tax.tax_group_id
            WHERE tax_group.l10n_uy_vat_code_bu NOTNULL
        """
    cr.execute(query)
    tax_ids = [tax.get('id') for tax in env.cr.dictfetchall()]
    env['account.tax'].browse(tax_ids).write({'l10n_uy_tax_category': 'vat'})

    # Cambio el plan de cuentas en 16 era uy_account en el modulo l10n_uy_account. Ahora en 17 el plan de cuentas esta
    # en l10n_uy y se llama 'uy'. Tenemos que actualizar este dato en la compañia porque si no cuando entramos al menu
    # de Ajustes recibimos este traceback https://gist.github.com/zaoral/461d737b35601c74d05ca3054d2f6e9f . Decidimos
    # pasarlo a vacio porque si le ponemeos "uy" como hay muchas diferencias entre los xml usados en una version y
    # otra puede traernos problemas en el futuro de duplicacion de registros que no queremos porque los xml son
    # distintos
    openupgrade.logged_query(env.cr, """
        UPDATE res_company
        SET
            chart_template = Null
        WHERE chart_template = 'uy_account'
    """)
