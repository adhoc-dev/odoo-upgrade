from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Running post-migrate script for l10n_uy_edi')
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Popular nueva tabla con datos en el account move
    openupgrade.logged_query(env.cr, """
    INSERT INTO l10n_uy_edi_document (move_id, state, uuid, message, request_datetime)
    SELECT
        move.id as move_id,
        move.l10n_uy_cfe_state_bu as state,
        move.l10n_uy_cfe_uuid_bu as uuid,
        move.l10n_uy_ucfe_msg_bu as message,
        TO_TIMESTAMP(TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'), 'YYYY-MM-DD HH24:MI:SS') as request_datetime
    FROM account_move move
    JOIN account_journal journal ON move.journal_id = journal.id
    WHERE journal.l10n_uy_edi_type = 'electronic' AND move.l10n_uy_cfe_state_bu NOTNULL
    """)

    openupgrade.logged_query(env.cr, """
    UPDATE ir_attachment SET 
        res_id = subc.edi_id,
        res_model = 'l10n_uy_edi.document',
        res_field = 'attachment_file'
    FROM (SELECT edi_doc.id AS edi_id, edi_doc.move_id from l10n_uy_edi_document edi_doc JOIN account_move ON account_move.id = edi_doc.move_id) as subc 
    WHERE subc.move_id = res_id AND name like '%.xml';
    """)

    for rec in env['l10n_uy_edi.document'].search([]):
      datas = env['ir.attachment'].search([('res_id', '=', rec.id), ('res_model', '=', 'l10n_uy_edi.document')]).datas
      if datas:
           rec.attachment_file = datas

    # Agregar relacion entre tabla edi document y move. campo 'l10n_uy_edi_document_id'
    openupgrade.logged_query(env.cr, """
        UPDATE account_move move
        SET
            l10n_uy_edi_document_id = edi.id
        FROM l10n_uy_edi_document AS edi
        WHERE edi.move_id = move.id
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE account_journal
        SET
            l10n_uy_edi_type = 'manual'
        WHERE  l10n_uy_edi_type = 'preprinted'
    """)

    # Actualizamos los select de los estados del cfe
    openupgrade.logged_query(env.cr, """
        UPDATE account_move
        SET
            l10n_uy_edi_cfe_state = 'error'
        WHERE l10n_uy_cfe_state_bu IN ('xml_error', 'connection_error', 'ucfe_error');
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE account_move
        SET
            l10n_uy_edi_cfe_state = Null
        WHERE l10n_uy_cfe_state_bu IN ('not_apply', 'draft_cfe');
    """)

    # Cambios en las addendas
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

    #TODO opcional: vincular las adendas con las facturas
    openupgrade.logged_query(env.cr, """
        INSERT INTO l10n_uy_edi_addenda (name, type, content, company_id)
        SELECT
            move.l10n_uy_additional_info_bu AS name,
            'cfe_doc' AS type,
            move.l10n_uy_additional_info_bu AS content,
            move.company_id AS company_id
        FROM account_move move
        WHERE move.l10n_uy_additional_info_bu NOTNULL
    """)

    openupgrade.logged_query(env.cr, """
        INSERT INTO l10n_uy_edi_addenda (name, type, content)
        SELECT
            product.l10n_uy_additional_info_pro_bu AS name,
            'item' AS type,
            product.l10n_uy_additional_info_pro_bu AS content
            -- product.product_tmpl_id.company_id AS company_id
        FROM product_product product
        WHERE product.l10n_uy_additional_info_pro_bu NOTNULL
    """)

    openupgrade.logged_query(env.cr, """
        INSERT INTO l10n_uy_edi_addenda (name, type, content, company_id)
        SELECT
            partner.l10n_uy_additional_info_part_bu AS name,
            'receiver' AS type,
            partner.l10n_uy_additional_info_part_bu AS content,
            partner.company_id AS company_id
        FROM res_partner partner
        WHERE partner.l10n_uy_additional_info_part_bu NOTNULL
    """)

    env['l10n_uy_edi.addenda'].search([('content', 'like', '{%}')]).is_legend = True

    # Seteamos los ambientes
    env['res.company'].search([('l10n_uy_edi_ucfe_env', '=', False)]).l10n_uy_edi_ucfe_env = 'demo'


    # Los re-creamos
    cron_ucfe_notif = env.ref('l10n_uy_edi.ir_cron_get_ucfe_notif', raise_if_not_found=False)
    cron_vendor_bills_received = env.ref('l10n_uy_edi.ir_cron_get_vendor_bills_received', raise_if_not_found=False)

    cron_ucfe_notif.unlink() if cron_ucfe_notif else False
    cron_vendor_bills_received.unlink() if cron_vendor_bills_received else False
