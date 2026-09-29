from odoo.addons.l10n_latam_check.models.account_payment_method import AccountPaymentMethod
import logging
_logger = logging.getLogger(__name__)


_get_payment_method_information = AccountPaymentMethod._get_payment_method_information


def _new_get_payment_method_information(self):
    """ Parcheamos este metodo para evitar error al crear diarios en el post. Esto pareciera ser un bug de odoo
    porque da error al crear nuevos diarios, no solo al editar el diario que se quiere chequear """
    # TODO si llega a ser necesario en el post podemos revertir esto
    _logger.info('disable new_third_party_checks creation')
    res = _get_payment_method_information(self)
    res['new_third_party_checks'] = {'mode': 'multi', 'domain': [('type', '=', 'dummy')]}
    return res


AccountPaymentMethod._get_payment_method_information = _new_get_payment_method_information


def migrate(env, version):
    pass
