import logging

from openupgradelib import openupgrade
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


def update_uruware_connection_info(env):
    _logger.info('Adaptar datos conexion test/prod uruware a nuevos campos del modulo UX')
    env.cr.execute('SELECT id, l10n_uy_ucfe_prod_env_bu, l10n_uy_ucfe_test_env_bu FROM res_company WHERE l10n_uy_ucfe_prod_env_bu NOT NULL;')
    connection_data = env.cr.dictfetchall()

    for rec in connection_data:
        company = env['res.company'].browse(rec.get('id'))
        prod_bu = safe_eval(rec.get('prod_bu'))
        test_bu = safe_eval(rec.get('l10n_uy_ucfe_test_env_bu'))

        company.l10n_uy_edi_ucfe_test_env = {
            'l10n_uy_edi_ucfe_commerce_code': test_bu.get('l10n_uy_ucfe_commerce_code'),
            'l10n_uy_edi_ucfe_password': test_bu.get('l10n_uy_ucfe_password'),
            'l10n_uy_edi_ucfe_terminal_code': test_bu.get('l10n_uy_ucfe_terminal_code'),
        }
        company.l10n_uy_edi_ucfe_prod_env = {
            'l10n_uy_edi_ucfe_commerce_code': prod_bu.get('l10n_uy_ucfe_commerce_code'),
            'l10n_uy_edi_ucfe_password': prod_bu.get('l10n_uy_ucfe_password'),
            'l10n_uy_edi_ucfe_terminal_code': prod_bu.get('l10n_uy_ucfe_terminal_code'),
        }


@openupgrade.migrate()
def migrate(env, version):
    update_uruware_connection_info(env)
