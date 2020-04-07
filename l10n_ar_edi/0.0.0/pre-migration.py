from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_field_renames = [
    ('account.move', 'account_move', 'afip_auth_verify_result', 'l10n_ar_afip_verification_result'),
    ('account.move', 'account_move', 'afip_auth_mode', 'l10n_ar_afip_auth_mode'),
    ('account.move', 'account_move', 'afip_auth_code', 'l10n_ar_afip_auth_code'),
    ('account.move', 'account_move', 'afip_auth_code_due', 'l10n_ar_afip_auth_code_due'),
    ('account.move', 'account_move', 'afip_xml_request', 'l10n_ar_afip_xml_request'),
    ('account.move', 'account_move', 'afip_xml_response', 'l10n_ar_afip_xml_response'),
    ('account.move', 'account_move', 'afip_result', 'l10n_ar_afip_result'),
    ('account.move', 'account_move', 'afip_fce_es_anulacion', 'l10n_ar_afip_fce_is_cancellation'),
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_ar')
    openupgrade.rename_fields(env, _field_renames)
