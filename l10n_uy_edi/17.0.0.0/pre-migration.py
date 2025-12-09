from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


# adenda viene de l10n_uy_account pero ahora esta en l10n_uy_edi
# Odoo ya crea el modelo nuevo al cargar el módulo actualizado, 
# por lo que NO debemos renombrar el modelo (causaría constraint violation)
# Solo necesitamos migrar los datos de la tabla vieja a la nueva

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


def migrate(cr, version):
    _logger.info('Running pre-migration script for l10n_uy_edi')
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Migrar tabla de adendas
    # Odoo ya crea el modelo y tabla nueva (l10n_uy_edi_addenda) al cargar el módulo
    # pero está vacía. La tabla vieja (l10n_uy_adenda) tiene los datos.
    # Estrategia: eliminar la tabla nueva vacía y renombrar la vieja
    if openupgrade.table_exists(cr, 'l10n_uy_adenda'):
        _logger.info('Migrating l10n_uy_adenda table')
        
        # Si existe la tabla nueva (creada por Odoo), eliminarla
        if openupgrade.table_exists(cr, 'l10n_uy_edi_addenda'):
            cr.execute("DROP TABLE l10n_uy_edi_addenda CASCADE")
            _logger.info('Dropped empty table l10n_uy_edi_addenda')
        
        # Renombrar la tabla vieja con los datos
        openupgrade.rename_tables(cr, [('l10n_uy_adenda', 'l10n_uy_edi_addenda')])
        _logger.info('Renamed table l10n_uy_adenda to l10n_uy_edi_addenda')
        
        # Eliminar el modelo viejo de ir_model para evitar conflictos
        cr.execute("DELETE FROM ir_model WHERE model = 'l10n.uy.adenda'")
        _logger.info('Removed old model l10n.uy.adenda from ir_model')

    # Backup de columnas antes de que se eliminen
    openupgrade.copy_columns(cr, _column_copy)

    # Eliminar columnas nuevas creadas por Odoo (vacías) para evitar conflictos con rename_fields
    # Odoo ya creó las columnas nuevas al cargar el módulo actualizado, pero están vacías.
    # Las columnas viejas tienen los datos, así que eliminamos las nuevas antes de renombrar.
    # NOTA: Solo para tablas que NO fueron eliminadas en el bloque anterior (ej: account_move, res_company)
    for model, table, old_field, new_field in _field_renames:
        # Saltar la tabla l10n_uy_edi_addenda porque ya la eliminamos completamente arriba
        if table == 'l10n_uy_edi_addenda':
            continue
        if openupgrade.table_exists(cr, table) and openupgrade.column_exists(cr, table, new_field):
            cr.execute(f'ALTER TABLE "{table}" DROP COLUMN "{new_field}" CASCADE')
            _logger.info('Dropped empty column %s.%s created by Odoo', table, new_field)

    # Renombrar campos usando openupgrade
    openupgrade.rename_fields(env, _field_renames)
