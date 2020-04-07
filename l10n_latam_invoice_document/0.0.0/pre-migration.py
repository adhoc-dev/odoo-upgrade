from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_model_renames = [
    ('account.document.type', 'l10n_latam.document.type'),
]

_table_renames = [
    ('account_document_type', 'l10n_latam_document_type'),
]

_field_renames = [
    ('account.move', 'account_move', 'document_type_id', 'l10n_latam_document_type_id'),
    ('account.move.line', 'account_move_line', 'document_type_id', 'l10n_latam_document_type_id'),
    ('account.journal', 'account_journal', 'use_documents', 'l10n_latam_use_documents'),
]

_xmlid_renames = [
    ('l10n_latam_invoice_document.report_decimal_price', 'account_payment_group_document.report_decimal_price'),
    ('l10n_ar_ux.dc_orden_pago_x', 'account_payment_group_document.dc_orden_pago_x'),
    ('l10n_ar_ux.dc_recibo_x', 'account_payment_group_document.dc_recibo_x'),
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_latam_invoice_document')
    openupgrade.rename_models(env.cr, _model_renames)
    openupgrade.rename_tables(env.cr, _table_renames)
    openupgrade.rename_fields(env, _field_renames)
    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move
        SET name = display_name
        WHERE name != display_name
        """)
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
