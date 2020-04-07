from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)

_model_renames = [
    ('old.model', 'new.model'),
]

_table_renames = [
    ('old_table', 'new_table'),
]

_field_renames = [
    ('account.move', 'account_move', 'document_type_id', 'l10n_latam_document_type_id'),
]

# tipically for data that has change it's xmlid
_xmlid_renames = [
]


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_ar')
    openupgrade.rename_models(env.cr, _model_renames)
    openupgrade.rename_tables(env.cr, _table_renames)
    openupgrade.rename_fields(env, _field_renames)
    openupgrade.logged_query(env.cr, """query""")
    openupgrade.rename_xmlids(env.cr, _xmlid_renames)
    # openupgrade.set_xml_ids_noupdate_value(
    #     env, "utm", [
    #         "campaign_stage_1",
    #         "campaign_stage_2",
    #         "campaign_stage_3",
    #     ],
    #     False,
    # )
