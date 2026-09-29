from odoo.addons.account_payment.models.account_journal import AccountJournal
import logging
_logger = logging.getLogger(__name__)


def _check_inbound_payment_method_line_ids(self):
    """ Parcheamos este metodo para evitar error al crear diarios en el post. Esto pareciera ser un bug de odoo
    porque da error al crear nuevos diarios, no solo al editar el diario que se quiere chequear """
    pass


AccountJournal._check_inbound_payment_method_line_ids = _check_inbound_payment_method_line_ids


def migrate(env, version):
    pass
