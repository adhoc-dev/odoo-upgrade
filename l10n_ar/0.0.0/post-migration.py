from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):

    # forzar actualizacion de la data de los tax groups y otras data
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/account_tax_group.xml')
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.country.csv')
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.currency.csv')
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/uom_uom_data.xml')
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_service_start = ai.afip_service_start
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_service_start is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_afip_service_end = ai.afip_service_end
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.afip_service_end is not null
        """)
    openupgrade.logged_query(env.cr, """
        UPDATE account_move AS am
        SET l10n_ar_currency_rate = ai.currency_rate
        FROM account_invoice AS ai
        WHERE ai.move_id = am.id and ai.currency_rate is not null
        """)
