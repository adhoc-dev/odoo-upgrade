from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


_table_renames = [
    ('account_check', 'account_check_bu'),
    ('account_check_operation', 'account_check_operation_bu'),
    ('account_checkbook', 'l10n_latam_checkbook'),
    ('account_check_account_payment_rel', 'account_check_account_payment_rel_bu'),
]

_model_renames = [
    ('account.checkbook', 'l10n_latam.checkbook'),
]

_column_copy = {
    'account_move': [('rejected_check_id', 'rejected_check_id_bu', None)],
    'res_company': [
        ('rejected_check_account_id', 'rejected_check_account_id_bu', None),
        ('deferred_check_account_id', 'deferred_check_account_id_bu', None),
        ('holding_check_account_id', 'holding_check_account_id_bu', None),
    ],
}

_field_renames = [
    # mejor lo hacemos en post copiando lo que efectivamente tiene el cheque ya que es lo que el usuario ve y seguro
    # está bien
    # ('account.payment', 'account_payment', 'check_bank_id', 'l10n_latam_check_bank_id'),
    # ('account.payment', 'account_payment', 'check_owner_vat', 'l10n_latam_check_issuer_vat'),
    # ('account.payment', 'account_payment', 'check_payment_date', 'l10n_latam_check_payment_date'),
    ('account.payment', 'account_payment', 'checkbook_id', 'l10n_latam_checkbook_id'),
]

# tipically for data that has change it's xmlid (vienen de l10n_latam_check porque el module rename ya los renombro)
_xmlid_renames = [
    ('l10n_latam_check.account_payment_method_received_third_check', 'l10n_latam_check.account_payment_method_in_third_party_checks'),
    ('l10n_latam_check.account_payment_method_delivered_third_check', 'l10n_latam_check.account_payment_method_out_third_party_checks'),
    # Esto lo hacemos en el modulo base antes de que se instale "account_check_printing"
    # ('l10n_latam_check.account_payment_method_issue_check', 'account_check_printing.account_payment_method_check'),
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_ar')

    # rename de checkbook que se mantiene parecido
    openupgrade.rename_models(env.cr, _model_renames)

    # backup de tables y checkbooks
    for old_table, new_table in _table_renames:
        if openupgrade.table_exists(env.cr, old_table):
            openupgrade.rename_tables(env.cr, [(old_table, new_table)])

    # aprovechamos campos existentes en payment con info del cheque
    openupgrade.rename_fields(env, _field_renames)

    # backup de columnas que nos interesan antes de que se borren
    openupgrade.copy_columns(env.cr, _column_copy)

    # copiamos numero de cheque a nuevo campo
    openupgrade.logged_query(
        env.cr, """UPDATE account_payment set check_number = check_name where check_name <> check_number""")

    # ayuda en desinstalación / aliminacion de modelo viejo
    openupgrade.logged_query(env.cr, """
        DElETE from ir_model_fields_selection
        USING ir_model_fields
        WHERE
            ir_model_fields_selection.field_id = ir_model_fields.id and
            ir_model_fields.model in ('account.check', 'account.checkbook', 'account.check.operation')
    """)

    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
