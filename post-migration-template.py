from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # map old / non existing value 'proforma' and 'proforma2' to value 'draft'
    openupgrade.map_values(
        env.cr,
        openupgrade.get_legacy_name('state'), 'state',
        [('proforma', 'draft'), ('proforma2', 'draft')],
        table='account_invoice', write='sql')
    openupgrade.logged_query(env.cr, """
        query
        """)

    openupgrade.load_data(
        env.cr, 'account', 'migrations/11.0.1.1/noupdate_changes.xml',
    )

    openupgrade.set_xml_ids_noupdate_value(
        env, "utm", [
            "campaign_stage_1",
            "campaign_stage_2",
            "campaign_stage_3",
        ],
        False,
    )
