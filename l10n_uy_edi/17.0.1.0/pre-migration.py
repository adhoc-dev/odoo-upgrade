from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


# adenda viene de l10n_uy_account pero ahora esta en l10n_uy_edi, no deberia haber problemas de que lo hagamos todo aca
# porque el borrado de lo que no va odoo lo hace al final
_table_renames = [
    ('l10n_uy_adenda', 'l10n_uy_edi_addenda'),
]

_model_renames = [
    ('l10n.uy.adenda', 'l10n_uy_edi.addenda'),
]

_column_copy = {
    'account_move': [
        ('l10n_uy_cfe_state', 'l10n_uy_cfe_state_bu', None),
        ('l10n_uy_cfe_uuid', 'l10n_uy_cfe_uuid_bu', None),
        ('l10n_uy_cfe_file', 'l10n_uy_cfe_file_bu', None),
        ('l10n_uy_ucfe_msg', 'l10n_uy_ucfe_msg_bu', None),
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_bu', None),
        ('l10n_uy_cfe_pdf', 'l10n_uy_cfe_pdf_bu', None),
    ],
    'account_tax_group': [
        ('l10n_uy_vat_code', 'l10n_uy_vat_code_bu', None),
    ],
    'product_product' : [
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_pro_bu', None),
    ],
    'res_partner' : [
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_part_bu', None),
    ]
}

_field_renames = [
    ('account.move', 'account_move', 'l10n_uy_cfe_state', 'l10n_uy_edi_cfe_state'),
    ('account.move', 'account_move', 'l10n_uy_cfe_file', 'l10n_uy_edi_xml_attachment_id'),
    ('account.move', 'account_move', 'l10n_uy_cfe_sale_mod', 'l10n_uy_edi_cfe_sale_mode'),
    ('account.move', 'account_move', 'l10n_uy_cfe_transport_route', 'l10n_uy_edi_cfe_transport_route'),

    ('account.journal', 'account_journal', 'l10n_uy_type', 'l10n_uy_edi_type'),

    ('res.company', 'res_company', 'l10n_uy_ucfe_env', 'l10n_uy_edi_ucfe_env'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_password', 'l10n_uy_edi_ucfe_password'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_commerce_code', 'l10n_uy_edi_ucfe_commerce_code'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_terminal_code', 'l10n_uy_edi_ucfe_terminal_code'),
    ('res.company', 'res_company', 'l10n_uy_dgi_house_code', 'l10n_uy_edi_branch_code'),
    ('res.company', 'res_company', 'l10n_uy_adenda_ids', 'l10n_uy_edi_addenda_ids'),

    ('l10n_uy_edi.addenda', 'l10n_uy_edi_addenda', 'legend_type', 'type'),
]


@openupgrade.migrate()
def migrate(env, version):
    # backup de columnas que nos interesan antes de que se borren
    _logger.debug('Running migrate script for l10n_uy_edi')

    openupgrade.rename_models(env.cr, _model_renames)

    for old_table, new_table in _table_renames:
        if openupgrade.table_exists(env.cr, old_table):
            openupgrade.rename_tables(env.cr, [(old_table, new_table)])

    openupgrade.copy_columns(env.cr, _column_copy)

    openupgrade.rename_fields(env, _field_renames)
