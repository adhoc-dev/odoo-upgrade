from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):

    # forzar actualizacion de la data de los tax groups y otras data
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/account_tax_group.xml')
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.country.csv')
    # openupgrade.load_data(env.cr, 'l10n_ar', 'data/res.currency.csv')
    openupgrade.load_data(env.cr, 'l10n_ar', 'data/uom_uom_data.xml')
