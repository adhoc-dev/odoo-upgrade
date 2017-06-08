# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenUpgrade module for Odoo
#    @copyright 2015-Today: Odoo Community Association
#    @author: Stephane LE CORNEC
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openupgradelib import openupgrade
# from openerp.addons.openupgrade_records.lib import apriori


renamed_modules = {
    # OCA/product-attribute
    'product_m2m_categories': 'product_multi_category',
    # OCA/e-commerce
    'product_links': 'product_multi_link',
    # OCA/sale-workflow
    'sale_exceptions': 'sale_exception',
    # OCA/partner-contact
    'partner_external_maps': 'partner_external_map',
    'partner_relations': 'partner_multi_relation',
    # OCA/server-tools
    'disable_openerp_online': 'disable_odoo_online',
    'inactive_session_timeout': 'auth_session_timeout',
    # OCA/runbot-addons
    'runbot_secure': 'runbot_relative',
    # not exactly a module rename, but they do the same
    'account_check_writing': 'account_check_printing',
    # OCA/account-invoicing
    'account_refund_original': 'account_invoice_refund_link',
    # 'l10n_ar_invoice': 'l10n_ar_account',
    # 'l10n_ar_base_vat': 'l10n_ar_partner',
    # OCA/social
    'marketing_security_group': 'mass_mailing_security_group',
    # ADHOC RENAMES
    'l10n_ar_invoice': 'account_document',
    'l10n_ar_partner_title': 'l10n_ar_partner',
    'l10n_ar_chart_generic': 'l10n_ar_chart',
    'l10n_ar_vat_ledger_city': 'l10n_ar_vat_ledger_citi',
    'l10n_ar_invoice_sale': 'l10n_ar_sale',
    'account_invoice_journal_filter': 'account_invoice_journal_group',
    'account_contract_lines_sequence': 'sale_contract_lines_sequence',
    'account_contract_prices_update': 'sale_contract_prices_update',
    'account_voucher_withholding': 'account_withholding',
    'account_voucher_withholding_automatic': 'account_withholding_automatic',
    # TODO ACTIVAR, todavia no lo queremos
    # 'l10n_ar_aeroo_voucher': 'l10n_ar_aeroo_payment_group',
    'purchase_uom_prices_uoms': 'product_purchase_uom',
    'product_template_search_by_ean13': 'product_template_search_by_barcode',
    'website_sale_l10n_ar_partner': 'l10n_ar_website_sale',
    'account_move_analytic': 'account_move_line_analytic_filters',
    'account_analytic_purchase_contract': 'purchase_contract',
    # OCA
    'account_financial_report_webkit': 'account_financial_report_qweb',
}


@openupgrade.migrate()
def migrate(cr, version):
    # openupgrade.logged_query(cr, """
    #     delete from ir_ui_view iv
    #     using ir_model_data d where iv.id=d.res_id
    #     and d.model = 'ir.ui.view'
    #     and d.module in ('account_document')
    #     """, ('l10n_ar_%',))

    # borramos todos los external ids que apuntan a vistas no qweb
    # por si alguno tiene no actualizable y entocnes no se recrea al borrar
    # vistas en proximo paso
    openupgrade.logged_query(cr, """
        DELETE FROM ir_model_data d
        USING ir_ui_view iv WHERE d.res_id = iv.id
        AND d.model = 'ir.ui.view' and iv.type != 'qweb'
    """)

    # borramos vistas no qweb para resolver multiples inconvenientes
    openupgrade.logged_query(cr, """
        DELETE FROM ir_ui_view where type != 'qweb'
    """)

    # por error relacionado con esto:
    # https://git.framasoft.org/framasoft/OCB/commit/31ff6c68f4b49d5c12e2487d369a338c51f8997b?view=parallel
    openupgrade.logged_query(cr, """
        DELETE FROM ir_model_data
        WHERE name = 'project_time_mode_id_duplicate_xmlid'
    """)

    # fir por l10n_ar_state desinstalado y errores en datos
    openupgrade.logged_query(cr, """
        UPDATE ir_model_data set noupdate=True WHERE
        model = 'res.country.state' and module = 'l10n_ar_states'
        """)

    # fix that afip should be no updatable
    openupgrade.logged_query(cr, """
        UPDATE ir_model_data set noupdate=True WHERE
        module = 'l10n_ar_invoice' and name = 'partner_afip'
        """)

    openupgrade.update_module_names(
        cr, renamed_modules.iteritems()
    )
