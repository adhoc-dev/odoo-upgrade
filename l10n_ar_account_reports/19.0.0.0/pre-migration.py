from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_column_copy = {
    'account_move_line': [
        ('tax_settlement_move_id', 'tax_settlement_move_id_bu', None),
        ('tax_state', 'tax_state_bu', None),
    ]
}

@openupgrade.migrate()
def migrate(env, version):
    _logger.info('Running pre-migrate script for l10n_ar_account_reports')
    openupgrade.copy_columns(env.cr, _column_copy)
