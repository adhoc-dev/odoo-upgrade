from oba import apply_module_changes

MERGE_MODULES = [
    # The invoice proposes the mandate in 20.0
    ("sale_subscription_direct_debit", "account_direct_debit_ux"),
]
RENAMED_MODULES = []
RENAMED_XMLIDS = []


def migrate(cr, version):
    apply_module_changes(cr, version, MERGE_MODULES, RENAMED_MODULES, RENAMED_XMLIDS)
