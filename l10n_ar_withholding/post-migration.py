from openupgradelib import openupgrade
import logging
_logger = logging.getLogger(__name__)


def migrate_payment_grup_data(env):
    """
    por ej. queremos mover "regimen_Retencion de apg a ap. Los ap tenían campo payment_group_id
    queremos pasar alguna especie de domain porque solo queremos pasarlo al pamynet que era retencion
    """
    # mover campos (excepto m2m)
    query = """
        update account_payment ap set
            unreconciled_amount = apg.unreconciled_amount,
            withholdable_advanced_amount = apg.withholdable_advanced_amount,
            retencion_ganancias = apg.retencion_ganancias,
            regimen_ganancias_id = apg.regimen_ganancias_id
        from account_payment_group_bu as apg
        where
            ap.payment_group_id_bu = apg.id
        """
    res = openupgrade.logged_query(env.cr, query)

    # popular to_pay_move_lines (m2m field, en post)
    query = """
        insert into account_move_line_payment_to_pay_rel (to_pay_line_id, payment_id)
        select
            rel.to_pay_line_id,  ap.id as payment_id
        from
            account_move_line_payment_group_to_pay_rel_bu rel
        join
            account_payment ap on ap.payment_group_id_bu = rel.payment_group_id
        """
    res = openupgrade.logged_query(env.cr, query)

    openupgrade.merge_models(env.cr, 'account.payment.group', 'account.payment', 'payment_group_id_bu')


def migrate_taxes_config(env):
    query = """update account_tax set
        type_tax_use = 'none',
        l10n_ar_withholding_payment_type = type_tax_use
    where
        type_tax_use in ('customer', 'supplier')
    """
    res = openupgrade.logged_query(env.cr, query)


def migrate_withholdings(env):
    # crear l10n_ar.payment.withholding
    # chequear que sean unicos!! (misma constraint que tenemos ahora)
    query = """
        insert into l10n_ar_payment_withholding
            (
                payment_id,
                name,
                tax_id,
                base_amount,
                amount,
                automatic,
                withholdable_invoiced_amount,
                withholdable_advanced_amount,
                accumulated_amount,
                total_amount,
                withholding_non_taxable_minimum,
                withholding_non_taxable_amount,
                withholdable_base_amount,
                period_withholding_amount,
                previous_withholding_amount,
                computed_withholding_amount,
                create_date,
                create_uid,
                write_date,
                write_uid
            )
        select
            ap.id as payment_id,
            withholding_number_bu as name,
            tax_withholding_id_bu as tax_id,
            withholding_base_amount_bu as base_amount,
            amount,
            automatic_bu,
            withholdable_invoiced_amount_bu,
            withholdable_advanced_amount_bu,
            accumulated_amount_bu,
            total_amount_bu,
            withholding_non_taxable_minimum_bu,
            withholding_non_taxable_amount_bu,
            withholdable_base_amount_bu,
            period_withholding_amount_bu,
            previous_withholding_amount_bu,
            computed_withholding_amount_bu,
            ap.create_date,
            ap.create_uid,
            ap.write_date,
            ap.write_uid
        from
            account_payment as ap
        join
            account_payment_method apm
        on
            apm.id = ap.payment_method_id
        where
            apm.code = 'withholding'
    """
    res = openupgrade.logged_query(env.cr, query)


@openupgrade.migrate()
def migrate(env, version):
    _logger.debug('Running migrate script for l10n_ar_withholding')
    migrate_payment_grup_data(env)
    migrate_withholdings(env)
    migrate_taxes_config(env)
