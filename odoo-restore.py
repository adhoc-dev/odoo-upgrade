from odoo.service.db import exp_saas_restore_db_from_odoo
request_nbr = '45221'
request_key = 'uU7X43cu7cfyqg7NP80H4A=='
db_name = 'test-upgrade'
exp_saas_restore_db_from_odoo('odoo', 'odoo', 'odoo', 'odoo', request_nbr, request_key, db_name)



dropdb pilotes && psql -c 'CREATE DATABASE "pilotes" ENCODING 'unicode' TEMPLATE "pilotes-bu"'

odoo --upgrade-path=$ODOO_UPGRADE_PATH -d pilotes -u all

LOS TODO DE CADA UNO
post desde upgrade lines
    cbu bank
    tratar de mapear algunas "debit_origin_id"?
    llevar a company
        llevar certificados de bases viejas (l10n_ar_afip_ws_key, l10n_ar_afip_ws_crt)
        l10n_ar_afip_verification_type
        l10n_ar_afip_ws_environment (ver de ajustar para que funque con server mode)
    llevar l10n_ar_ncm_code ? al menos poner en release de cambios
    borrar estos doc types? 
        dc_inv,,INVOICE,INVOICE,invoice,IN ,generic,True
        dc_cn,,CREDIT NOTE,CREDIT NOTE,credit_note,CN ,generic,True
        dc_dn,,DEBIT NOTE,DEBIT NOTE,debit_note,DB ,generic,True
        dc_inv_disc,,INVOICE (Tax Disc.),INVOICE,,IN ,generic,False
        dc_cn_disc,,CREDIT NOTE (Tax Disc.),CREDIT NOTE,,CN ,generic,False
        dc_dn_disc,,DEBIT NOTE (Tax Disc.),DEBIT NOTE,,DB ,generic,False
    borrar tax_group_iva_gravado? existe

    # map sequences journal (    l10n_latam_journal_id y l10n_latam_document_type_id

    # computar l10n_ar_afip_pos_system (samos point_of_sale_type y ), l10n_ar_afip_pos_partner_id?, l10n_ar_share_sequences
        #  usar campo afip_ws tmb (lo hacemos en edi?)
        # document_sequence_type --> own_sequence, same_sequence a shared sequence (afip_ws)
    # migrate data 
    # mapping de selection: ('multilateral', 'Multilateral'),
            # ('local', 'Local'),
            # ('no_liquida', 'No Liquida'),
            # [('multilateral', 'Multilateral'), ('local', 'Local'), ('exempt', 'Exempt')],

    probar y arreglar load de 
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.country.csv')
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.currency.csv')

    # arreglar ordne de pago ORDEN DE PAGO X y recibo?

    arreglar end upgrade

# TODO mapear l10n_ar_afip_result (de factura electronica)


1. compartir archivo
2. explicar boostrap, columnas y usos tipicos que sea hacen en odoo


testar
    forzar load data de
        tax gorups (son no update) (forzar) LISTO
        document type (converitr a updateables) 
        afip.responsability.type (Convertir a updateables)
        recargar mas data de countrries (res.country.csv)? y monedas (res.currency.csv) uoms (uom_uom_data.xml)?

    fiscal positions afip_responsability_type_ids --> l10n_ar_afip_responsibility_type_ids
