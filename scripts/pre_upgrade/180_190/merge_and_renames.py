from oba import apply_module_changes

MERGE_MODULES = [
    ("l10n_ar_tax_ratio", "l10n_ar_tax"),
    ("sale_exceptions_ignore_approve", "sale_exception_ux"),
    ("sale_three_discounts", "sale_triple_discount"),
    ("l10n_ar_stock_custom", "l10n_ar_stock"),
    ("l10n_ar_stock_adhoc", "l10n_ar_stock"),
    ("payment_redsys_oca", "payment_redsys"),
    ("l10n_uy_edi_stock_custom", "l10n_uy_edi_stock"),
]
RENAMED_MODULES = []
RENAMED_XMLIDS = [("payment_redsys.redsys_form", "payment_redsys.redirect_form")]


def migrate(cr, version):
    apply_module_changes(cr, version, MERGE_MODULES, RENAMED_MODULES, RENAMED_XMLIDS)
