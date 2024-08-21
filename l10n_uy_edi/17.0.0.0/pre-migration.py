from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


_table_renames = [
    ('account_move', 'account_move_bu'),
    ('l10n.uy.adenda', 'l10n_uy_edi.addenda'),
]

_field_renames = [
    ('account.move', 'account_move', 'l10n_uy_cfe_state', 'l10n_uy_edi_cfe_state'),
    ('account.move', 'account_move', 'l10n_uy_cfe_file', 'l10n_uy_edi_xml_attachment_id'),
    ('account.move', 'account_move', 'l10n_uy_cfe_pdf', 'invoice_pdf_report_file'),
    ('account.move', 'account_move', 'l10n_uy_cfe_sale_mod', 'l10n_uy_edi_cfe_sale_mode'),
    ('account.move', 'account_move', 'l10n_uy_cfe_transport_route', 'l10n_uy_edi_cfe_transport_route'),

    ('account.journal', 'account_journal', 'l10n_uy_type', 'l10n_uy_edi_type'),

    ('res.company', 'res_company', 'l10n_uy_ucfe_env', 'l10n_uy_edi_ucfe_env'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_password', 'l10n_uy_edi_ucfe_password'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_commerce_code', 'l10n_uy_edi_ucfe_commerce_code'),
    ('res.company', 'res_company', 'l10n_uy_ucfe_terminal_code', 'l10n_uy_edi_ucfe_terminal_code'),
    ('res.company', 'res_company', 'l10n_uy_dgi_house_code', 'l10n_uy_edi_branch_code'),
    ('res.company', 'res_company', 'l10n_uy_adenda_ids', 'l10n_uy_edi_addenda_ids'),


@openupgrade.migrate()
def migrate(env, version):
    # backup de columnas que nos interesan antes de que se borren
    _logger.debug('Running migrate script for l10n_uy_edi')

    # Popular nueva tabla con datos en el account move
    openupgrade.logged_query(env.cr, """
        INSERT INTO l10n_uy_edi_document (name, move_id, state, uuid, attachment_id, message)
        SELECT
            name as name,
            id as move_id,
            l10n_uy_cfe_state as state,
            l10n_uy_cfe_uuid as uuid,
            l10n_uy_cfe_file as attachment_id,
            l10n_uy_ucfe_msg as message,
        FROM account_move move
        WHERE move.journal_id.l10n_uy_edi_type == 'electronic'
    """)
    # TODO
    # attachment_file → campo binary. no existe ¿Cómo popular?
    # request_datetime (campo requerido, dejar valor por defecto para los viejos?)

    # Agregar relacion entre tabla edi document y move. campo 'l10n_uy_edi_document_id'
    openupgrade.logged_query(env.cr, """
        UPDATE account_move move
        SET
            l10n_uy_edi_document_id = edi.id
        FROM l10n_uy_edi_document AS edi
        WHERE edi.move_id == move.id'
    """)
