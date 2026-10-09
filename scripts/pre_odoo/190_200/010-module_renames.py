import logging

_logger = logging.getLogger(__name__)

# Ours in 19.0, Odoo's in 20.0 under the same name: renamed straight to its 20.0 name so
# Odoo's platform keeps its hands off our fields. The other half:
# scripts/pre_upgrade/190_200/account_direct_debit_mandates.py.
MODULE_RENAMES = [
    ("account_direct_debit", "account_direct_debit_ux"),
]


def migrate(cr, version):
    """Rename the MODULE_RENAMES modules in the source database, before the dump to Odoo.

    Same SQL as scripts/pre_odoo/180_190/020-module_renames.py; a no-op when the module is
    not in the database.
    """
    for old, new in MODULE_RENAMES:
        _logger.info("Renaming module %s to %s", old, new)
        cr.execute("UPDATE ir_module_module SET name = %s WHERE name = %s", (new, old))
        cr.execute(
            """
            UPDATE ir_model_data
               SET name = %s
             WHERE name = %s AND module = 'base' AND model = 'ir.module.module'
            """,
            ("module_%s" % new, "module_%s" % old),
        )
        cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", (new, old))
        cr.execute(
            "UPDATE ir_module_module_dependency SET name = %s WHERE name = %s",
            (new, old),
        )
