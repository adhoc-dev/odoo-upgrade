from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    # Popular nueva tabla con datos en el account move
    openupgrade.logged_query(env.cr, """
        INSERT INTO l10n_uy_edi_document (name, move_id, state, uuid, attachment_id, message)
        SELECT
            name as name,
            id as move_id,
            l10n_uy_cfe_state_bu as state,
            l10n_uy_cfe_uuid_bu as uuid,
            l10n_uy_ucfe_msg_bu as message
        FROM account_move move
        WHERE move.journal_id.l10n_uy_edi_type == 'electronic'
    """)

    # l10n_uy_cfe_file_bu as attachment_id,
    # TODO
    # attachment_file → campo binary. no existe ¿Cómo popular?
    # request_datetime (campo requerido, dejar valor por defecto para los viejos?)

    # Agregar relacion entre tabla edi document y move. campo 'l10n_uy_edi_document_id'
    openupgrade.logged_query(env.cr, """
        UPDATE account_move move
        SET
            l10n_uy_edi_document_id = edi.id
        FROM l10n_uy_edi_document AS edi
        WHERE edi.move_id == move.id
    """)

    # update account_move set state = xml_error where not_apply
    # Quitamos opciones opciones
    # Lo que era  'xml_error', 'connection_error', 'ucfe_error' ahora sería "error"
    # Lo que era 'not_apply', 'draft_cfe' poner vacio
    openupgrade.logged_query(env.cr, """
        UPDATE account_move
        SET
            l10n_uy_edi_cfe_state = 'error'
        FROM account_move
        WHERE l10n_uy_cfe_state_bu IN ('xml_error', 'connection_error', 'ucfe_error');
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE account_move
        SET
            l10n_uy_edi_cfe_state = Null
        FROM account_move
        WHERE l10n_uy_cfe_state_bu IN ('not_apply', 'draft_cfe');
    """)

    # TODO implementar query de actualizar esto, tal vez en post vaya bien?
    # legend_type → type
    # Cambiaron opciones
    # 'emisor' →"issuer" 
    # 'receptor' →  "receiver"
    # 'comprobante' →  "cfe_doc"
    # 'adenda' →  "addenda"
    openupgrade.logged_query(env.cr, """
        UPDATE l10n_uy_edi_addenda
        SET
            type = 'issuer'
        WHERE type = 'emisor'
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE l10n_uy_edi_addenda
        SET
            type = 'receiver'
        WHERE type = 'receptor'
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE l10n_uy_edi_addenda
        SET
            type = 'cfe_doc'
        WHERE type = 'comprobante'
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE l10n_uy_edi_addenda
        SET
            type = 'addenda'
        WHERE type = 'adenda'
    """)

    # convertimos nuestro "l10n_uy_cfe_file_bu" m2o a ir.attachment a un campo binary "attachment_file"
    for move in electronic_move_with_l10n_uy_cfe_file_bu:
        move.l10n_uy_cfe_file_bu.write({
            'res_id': move.l10n_uy_edi_document_id.id,
            # lo del name podria ser evitable
            'name': move.l10n_uy_edi_document_id._get_xml_attachment_name(),
            'res_model': 'l10n_uy_edi.document',
            'res_field': 'attachment_file',
        })

    # TODO implementar
    # logged_query
    # insert into adendas SELECT
    #         name as name,
    #         select l10n_uy_additional_info_bu from account_move where l10n_uy_additional_info_bu is not null

    # TODO implementar para este caso de partners tmb l10n_uy_additional_info
    # logged_query
    # insert into adendas SELECT
    #         name as name,
    #         select l10n_uy_additional_info_bu from account_move where l10n_uy_additional_info_bu is not null

    env['res.company'].search(l10n_uy_edi_ucfe_env = False).l10n_uy_edi_ucfe_env = 'demo'
    env['l10n_uy_edi.addenda'].search(name like '{').is_legend = True

    # update account_tax set l10n_uy_tax_category = bla from tax_group where
    # tax.tax_group_id = tax_group.id 
    # and l10n_uy_tax_category_bu is not null


    env.ref('l10n_uy_edi.ir_cron_get_ucfe_notif').unlink()
    # lo re-creamos
    env.ref('l10n_uy_edi.ir_cron_get_vendor_bills_received').unlink()
