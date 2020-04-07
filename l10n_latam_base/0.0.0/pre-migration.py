from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_model_renames = [
    ('res.partner.id_category', 'l10n_latam.identification.type'),
]

_field_renames = [
    ('res.partner', 'res_partner', 'main_id_category_id', 'l10n_latam_identification_type_id'),
]

_table_renames = [
    ('res_partner_id_category', 'l10n_latam_identification_type'),
]

_xmlid_renames = [
    # move models from account_document to account_payment_group_document
    ('l10n_latam_base.dt_PAS', 'l10n_latam_base.it_pass'),
    ('l10n_latam_base.dt_CIe', 'l10n_latam_base.it_fid'),
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_latam_base')
    openupgrade.rename_models(env.cr, _model_renames)
    openupgrade.rename_tables(env.cr, _table_renames)
    openupgrade.rename_fields(env, _field_renames)
    openupgrade.logged_query(env.cr, """
        UPDATE res_partner
        SET vat = main_id_number
        WHERE main_id_number is not null
        """)
    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
