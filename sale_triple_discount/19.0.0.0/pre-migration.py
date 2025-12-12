from odoo.upgrade.util.fields import move_field_to_module


def migrate(cr, version):
    fields = ["discoun1", "discoun2", "discoun3"]
    for field in fields:
        move_field_to_module(cr, "account.move.line", field, "sale_three_discounts", "account_invoice_triple_discount")
