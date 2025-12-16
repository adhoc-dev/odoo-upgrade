from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


# adenda viene de l10n_uy_account pero ahora esta en l10n_uy_edi, no deberia haber problemas de que lo hagamos todo aca
# porque el borrado de lo que no va odoo lo hace al final
_table_renames = [
    ('l10n_uy_adenda', 'l10n_uy_addenda_bu'),
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
    'product_product' : [
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_pro_bu', None),
    ],
    'res_partner' : [
        ('l10n_uy_additional_info', 'l10n_uy_additional_info_part_bu', None),
    ]
}

_field_copy = [
    ('account_move', 'l10n_uy_cfe_state', 'l10n_uy_edi_cfe_state'),
    # ('account_move', 'l10n_uy_cfe_file', 'l10n_uy_edi_xml_attachment_id'),
    ('account_move', 'l10n_uy_cfe_sale_mod', 'l10n_uy_edi_cfe_sale_mode'),
    ('account_move', 'l10n_uy_cfe_transport_route', 'l10n_uy_edi_cfe_transport_route'),
    ('account_journal', 'l10n_uy_type', 'l10n_uy_edi_type'),
    ('res_company', 'l10n_uy_ucfe_env', 'l10n_uy_edi_ucfe_env'),
    ('res_company', 'l10n_uy_ucfe_password', 'l10n_uy_edi_ucfe_password'),
    ('res_company', 'l10n_uy_ucfe_commerce_code', 'l10n_uy_edi_ucfe_commerce_code'),
    ('res_company', 'l10n_uy_ucfe_terminal_code', 'l10n_uy_edi_ucfe_terminal_code'),
    ('res_company', 'l10n_uy_dgi_house_code', 'l10n_uy_edi_branch_code'),
    # ('res_company', 'l10n_uy_adenda_ids', 'l10n_uy_edi_addenda_ids'),
    # ('l10n_uy_edi_addenda', 'legend_type', 'type'),
]

def migrate(cr, version):
    # backup de columnas que nos interesan antes de que se borren
    _logger.info('Running migrate script for l10n_uy_edi')
    env = api.Environment(cr, SUPERUSER_ID, {})

    env.cr.execute("""
        ALTER TABLE account_move
        DROP COLUMN IF EXISTS l10n_uy_idreq;
    """)

    for old_table, new_table in _table_renames:
        if openupgrade.table_exists(env.cr, old_table):
            openupgrade.rename_tables(env.cr, [(old_table, new_table)])

    openupgrade.copy_columns(env.cr, _column_copy)

    env.cr.execute("""INSERT INTO l10n_uy_edi_addenda (
      company_id, content, create_date, create_uid, id, name, type, write_date, write_uid
    )
    SELECT
      company_id, content, create_date, create_uid, id, name, legend_type, write_date, write_uid
    FROM l10n_uy_adenda""")
    for item in _field_copy:
        table_name, bu_name, new_field_name = item
        env.cr.execute("""
            UPDATE %s
            SET %s = %s;""" % (table_name, new_field_name, bu_name))
