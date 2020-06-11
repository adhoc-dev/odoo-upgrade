from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_model_renames = [
    ('afip.responsability.type', 'l10n_ar.afip.responsibility.type'),
]

_table_renames = [
    ('afip_responsability_type', 'l10n_ar_afip_responsibility_type'),
    ('afip_reponsbility_account_fiscal_pos_rel', 'l10n_ar_afip_reponsibility_type_fiscal_pos_rel'),
]

_field_renames = [
    ('account.move', 'account_move', 'afip_responsability_type_id', 'l10n_ar_afip_responsibility_type_id'),
    ('account.journal', 'account_journal', 'point_of_sale_number', 'l10n_ar_afip_pos_number'),
    ('l10n_latam.identification.type', 'account_journal', 'point_of_sale_number', 'l10n_ar_afip_code'),
    ('res.country', 'res_country', 'afip_code', 'l10n_ar_afip_code'),
    ('res.currency', 'res_currency', 'afip_code', 'l10n_ar_afip_code'),
    ('uom.uom', 'uom_uom', 'afip_code', 'l10n_ar_afip_code'),
    ('res.partner', 'res_partner', 'gross_income_number', 'l10n_ar_gross_income_number'),
    ('res.partner', 'res_partner', 'gross_income_type', 'l10n_ar_gross_income_type'),
    ('res.partner', 'res_partner', 'afip_responsability_type_id', 'l10n_ar_afip_responsibility_type_id'),
    ('account.fiscal.position', 'account_fiscal_position', 'afip_responsability_type_ids', 'l10n_ar_afip_responsibility_type_ids'),
]

_column_renames = {
    'l10n_ar_afip_reponsibility_type_fiscal_pos_rel': [
        ('position_id', 'account_fiscal_position_id'),
        ('afip_responsability_type_id', 'l10n_ar_afip_responsibility_type_id'),
    ],
}

_xmlid_renames = [
    # move models from l10n_ar_account to l10n_ar_ux
    ('l10n_ar.model_afip_concept', 'l10n_ar_ux.model_afip_concept'),
    ('l10n_ar.model_afip_activity', 'l10n_ar_ux.model_afip_activity'),
    ('l10n_ar.model_afip_tax', 'l10n_ar_ux.model_afip_tax'),

    # renombrar tax groups
    # al final el modulo l10n_ar_account se renombro a l10n_ar_ux, por eso hacemos arl revx
    ('l10n_ar_ux.tax_group_percepcion_drei', 'l10n_ar.tax_group_percepcion_municipal'),
    ('l10n_ar_ux.tax_impuestos_internos', 'l10n_ar.tax_impuestos_internos'),
    ('l10n_ar_ux.tax_group_iva_no_corresponde', 'l10n_ar.tax_group_iva_no_corresponde'),
    ('l10n_ar_ux.tax_group_iva_no_gravado', 'l10n_ar.tax_group_iva_no_gravado'),
    ('l10n_ar_ux.tax_group_iva_exento', 'l10n_ar.tax_group_iva_exento'),
    ('l10n_ar_ux.tax_group_iva_0', 'l10n_ar.tax_group_iva_0'),
    ('l10n_ar_ux.tax_group_iva_10', 'l10n_ar.tax_group_iva_105'),
    ('l10n_ar_ux.tax_group_iva_21', 'l10n_ar.tax_group_iva_21'),
    ('l10n_ar_ux.tax_group_iva_27', 'l10n_ar.tax_group_iva_27'),
    ('l10n_ar_ux.tax_group_iva_5', 'l10n_ar.tax_group_iva_5'),
    ('l10n_ar_ux.tax_group_iva_25', 'l10n_ar.tax_group_iva_025'),
    ('l10n_ar_ux.tax_group_percepcion_iva', 'l10n_ar.tax_group_percepcion_iva'),
    ('l10n_ar_ux.tax_group_percepcion_ganancias', 'l10n_ar.tax_group_percepcion_ganancias'),
    ('l10n_ar_ux.tax_group_percepcion_iibb', 'l10n_ar.tax_group_percepcion_iibb'),
    # afip respon
    ('l10n_ar_ux.res_IVARI', 'l10n_ar.res_IVARI'),
    ('l10n_ar_ux.res_IVARNI', 'l10n_ar.res_IVARNI'),
    ('l10n_ar_ux.res_IVANR', 'l10n_ar.res_IVANR'),
    ('l10n_ar_ux.res_IVAE', 'l10n_ar.res_IVAE'),
    ('l10n_ar_ux.res_CF', 'l10n_ar.res_CF'),
    ('l10n_ar_ux.res_RM', 'l10n_ar.res_RM'),
    ('l10n_ar_ux.res_NOCATEG', 'l10n_ar.res_NOCATEG'),
    ('l10n_ar_ux.res_CLI_EXT', 'l10n_ar.res_EXT'),
    ('l10n_ar_ux.res_IVA_LIB', 'l10n_ar.res_IVA_LIB'),
    ('l10n_ar_ux.res_IVARI_AP', 'l10n_ar.res_IVARI_AP'),
    ('l10n_ar_ux.res_EVENTUAL', 'l10n_ar.res_EVENTUAL'),
    ('l10n_ar_ux.res_MON_SOCIAL', 'l10n_ar.res_MON_SOCIAL'),
    ('l10n_ar_ux.res_EVENTUAL_SOCIAL', 'l10n_ar.res_EVENTUAL_SOCIAL'),
    # identification types que van a l10n_ar (importante hacerlo aca)
    ('l10n_latam_base.dt_CUIT', 'l10n_ar.it_cuit'),
    ('l10n_latam_base.dt_DNI', 'l10n_ar.it_dni'),
    ('l10n_latam_base.dt_CUIL', 'l10n_ar.it_CUIL'),
    ('l10n_latam_base.dt_Sigd', 'l10n_ar.it_Sigd'),
    ('l10n_latam_base.dt_CPF', 'l10n_ar.it_CPF'),
    ('l10n_latam_base.dt_CBA', 'l10n_ar.it_CBA'),
    ('l10n_latam_base.dt_CCat', 'l10n_ar.it_CCat'),
    ('l10n_latam_base.dt_CCor', 'l10n_ar.it_CCor'),
    ('l10n_latam_base.dt_CCorr', 'l10n_ar.it_CCorr'),
    ('l10n_latam_base.dt_CIER', 'l10n_ar.it_CIER'),
    ('l10n_latam_base.dt_CIJ', 'l10n_ar.it_CIJ'),
    ('l10n_latam_base.dt_CIMen', 'l10n_ar.it_CIMen'),
    ('l10n_latam_base.dt_CILR', 'l10n_ar.it_CILR'),
    ('l10n_latam_base.dt_CIS', 'l10n_ar.it_CIS'),
    ('l10n_latam_base.dt_CISJ', 'l10n_ar.it_CISJ'),
    ('l10n_latam_base.dt_CISL', 'l10n_ar.it_CISL'),
    ('l10n_latam_base.dt_CISF', 'l10n_ar.it_CISF'),
    ('l10n_latam_base.dt_CISdE', 'l10n_ar.it_CISdE'),
    ('l10n_latam_base.dt_CIT', 'l10n_ar.it_CIT'),
    ('l10n_latam_base.dt_CICha', 'l10n_ar.it_CICha'),
    ('l10n_latam_base.dt_CIChu', 'l10n_ar.it_CIChu'),
    ('l10n_latam_base.dt_CIF', 'l10n_ar.it_CIF'),
    ('l10n_latam_base.dt_CIMis', 'l10n_ar.it_CIMis'),
    ('l10n_latam_base.dt_CIN', 'l10n_ar.it_CIN'),
    ('l10n_latam_base.dt_CILP', 'l10n_ar.it_CILP'),
    ('l10n_latam_base.dt_CIRN', 'l10n_ar.it_CIRN'),
    ('l10n_latam_base.dt_CISC', 'l10n_ar.it_CISC'),
    ('l10n_latam_base.dt_CITdF', 'l10n_ar.it_CITdF'),
    ('l10n_latam_base.dt_CDI', 'l10n_ar.it_CDI'),
    ('l10n_latam_base.dt_LE', 'l10n_ar.it_LE'),
    ('l10n_latam_base.dt_LC', 'l10n_ar.it_LC'),
    ('l10n_latam_base.dt_ET', 'l10n_ar.it_ET'),
    ('l10n_latam_base.dt_AN', 'l10n_ar.it_AN'),
    ('l10n_latam_base.dt_CIBAR', 'l10n_ar.it_CIBAR'),
    ('l10n_latam_base.dt_CdM', 'l10n_ar.it_CdM'),
    ('l10n_latam_base.dt_UpApP', 'l10n_ar.it_UpApP'),
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_ar')
    openupgrade.rename_models(env.cr, _model_renames)
    openupgrade.rename_tables(env.cr, _table_renames)
    openupgrade.rename_fields(env, _field_renames)
    openupgrade.rename_xmlids(env.cr, _xmlid_renames)

    # rename exml ids que podrian no estar mas
    try:
        openupgrade.rename_xmlids(env.cr, [
            ('l10n_ar_ux.par_cfa', 'l10n_ar.par_cfa'),
            ('l10n_ar_ux.par_iibb_pagar', 'l10n_ar.par_iibb_pagar'),
            ('l10n_ar_ux.partner_afip', 'l10n_ar.partner_afip')])
    except Exception as e:
        _logger.debug('No pudimos actualizar xml ids de algunos partners, probablemente se borraron')

    # rename de columnas de fiscal position
    openupgrade.rename_columns(env.cr, _column_renames)

    # pasamos los doc types que se renombraron a l10n_ar_ux a l10n_ar
    # tmb los marcamos actualziables
    openupgrade.logged_query(env.cr, """
        UPDATE ir_model_data
        SET module = 'l10n_ar', noupdate = False
        WHERE module = 'l10n_ar_ux' and model = 'l10n_latam.document.type'
        """)

    # poner afip resp type como actualizable res_EXT
    openupgrade.logged_query(env.cr, """
        UPDATE ir_model_data
        SET noupdate = False
        WHERE model = 'l10n_ar.afip.responsibility.type'
        """)
