from openupgradelib import openupgrade, openupgrade_merge_records


@openupgrade.migrate()
def migrate(env, version):
    # sincronizacion de commercial fields
    # patch the dni validation para que no de error
    from odoo.addons.l10n_ar.models import res_partner
    res_partner.ResPartner.l10n_ar_identification_validation = lambda x: True
    companies = env['res.partner'].search(
        [('child_ids', '!=', False), '|', ("parent_id", "=", False), ("is_company", "=", True)])
    for company in companies:
        company._commercial_sync_to_children()
