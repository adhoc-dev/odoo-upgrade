from openupgradelib import openupgrade, openupgrade_merge_records


@openupgrade.migrate()
def migrate(env, version):

    org = env.ref('l10n_ar_ux.res_EXT', False)
    dest = env.ref('l10n_ar.res_EXT', False)
    if org and dest:
        openupgrade_merge_records.merge_records(env, 'l10n_ar.afip.responsibility.type', org.ids, dest.id)

    org = env.ref('l10n_ar_ux.res_IVARIFM', False)
    dest = env.ref('l10n_ar.res_IVARI', False)
    if org and dest:
        openupgrade_merge_records.merge_records(env, 'l10n_ar.afip.responsibility.type', org.ids, dest.id)
