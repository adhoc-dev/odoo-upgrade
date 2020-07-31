from openupgradelib import openupgrade, openupgrade_merge_records


@openupgrade.migrate()
def migrate(env, version):
    # sincronizacion de commercial fields
    companies = env['res.partner'].search([('child_ids', '!=', False), '|', ("parent_id", "=", False), ("is_company", "=", True)])
    for company in companies:
        company._commercial_sync_to_children()
