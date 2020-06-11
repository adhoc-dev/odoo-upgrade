from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):

    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_verification_result = ai.afip_auth_verify_result
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_auth_verify_result is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_auth_mode = ai.afip_auth_mode
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_auth_mode is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_auth_code = ai.afip_auth_code
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_auth_code is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_auth_code_due = ai.afip_auth_code_due
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_auth_code_due is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_xml_request = ai.afip_xml_request
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_xml_request is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_xml_response = ai.afip_xml_response
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_xml_response is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_result = ai.afip_result
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_result is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_fce_is_cancellation = ai.afip_fce_es_anulacion
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_fce_es_anulacion is not null
        """)
