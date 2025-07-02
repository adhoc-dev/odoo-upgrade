from openupgradelib import openupgrade
from odoo import SUPERUSER_ID, api
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info('Running post-migrate script for l10n_uy_edi_stock')
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Popular nueva tabla con datos en el stock picking
    openupgrade.logged_query(env.cr, """
    INSERT INTO l10n_uy_edi_document (picking_id, state, uuid, message, request_datetime)
    SELECT
        picking.id as picking_id,
        picking.l10n_uy_cfe_state_bu as state,
        picking.l10n_uy_cfe_uuid_bu as uuid,
        picking.l10n_uy_ucfe_msg_bu as message,
        TO_TIMESTAMP(TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'), 'YYYY-MM-DD HH24:MI:SS') as request_datetime
    FROM stock_picking picking
    WHERE picking.l10n_uy_cfe_state_bu is NOT NULL
    """)

    # Mover attachment del picking al registro del edi document model
    openupgrade.logged_query(env.cr, """
    UPDATE ir_attachment SET
        res_id = subc.edi_id,
        res_model = 'l10n_uy_edi.document',
        res_field = 'attachment_file'
    FROM (
        SELECT edi_doc.id AS edi_id, edi_doc.picking_id
        FROM l10n_uy_edi_document edi_doc
        JOIN stock_picking ON stock_picking.id = edi_doc.picking_id) as subc
    WHERE subc.picking_id = res_id AND name like '%.xml';
    """)

    # Re computar datas (campo binary con el nuevo cambio del attachment_id
    for rec in env['l10n_uy_edi.document'].search([]):
        datas = env['ir.attachment'].search([('res_id', '=', rec.id), ('res_model', '=', 'l10n_uy_edi.document')]).datas
        if datas:
            rec.attachment_file = datas

    # Agregar relacion entre tabla edi document y picking. campo 'l10n_uy_edi_document_id'
    openupgrade.logged_query(env.cr, """
        UPDATE stock_picking picking
        SET
            l10n_uy_edi_document_id = edi.id
        FROM l10n_uy_edi_document AS edi
        WHERE edi.picking_id = picking.id
    """)

    # Actualizamos los select de los estados del cfe
    openupgrade.logged_query(env.cr, """
        UPDATE stock_picking
        SET
            l10n_uy_edi_cfe_state = 'error'
        WHERE l10n_uy_cfe_state_bu IN ('xml_error', 'connection_error', 'ucfe_error');
    """)

    openupgrade.logged_query(env.cr, """
        UPDATE stock_picking
        SET
            l10n_uy_edi_cfe_state = Null
        WHERE l10n_uy_cfe_state_bu IN ('not_apply', 'draft_cfe');
    """)

    # TODO opcional: vincular las adendas con las facturas
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
