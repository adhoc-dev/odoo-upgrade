from odoo.upgrade import util


def migrate(cr, version):
    if not util.column_exists(cr, "sale_order_type", "invoice_company_id"):
        util.create_column(cr, "sale_order_type", "invoice_company_id", "INTEGER")
