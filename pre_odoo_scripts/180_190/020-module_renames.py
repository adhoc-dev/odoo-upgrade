import logging

_logger = logging.getLogger(__name__)

# Modulos que en 18.0 son nuestros y en 19.0 pasaron a existir en Odoo con el mismo nombre
# tecnico (por eso en 19.0 los nuestros se renombraron a `_ux`). Si la base llega a Odoo con
# el nombre real, su plataforma actualiza el registro como si fuera el suyo y nuestras vistas
# quedan referenciando campos que el modulo de Odoo no define. Renombrados no los conoce y
# los deja intactos; el nombre real se repone del otro lado, en
# pre_upgrade_scripts/180_190/merge_and_renames.py.
MODULE_RENAMES = [
    ("l10n_ar_stock", "l10n_ar_stock_custom"),
    ("l10n_uy_edi_stock", "l10n_uy_edi_stock_custom"),
]


def migrate(cr, version):
    """Renombra los modulos de MODULE_RENAMES en la base vieja, antes del dump a Odoo.

    Equivalente en SQL del rename de `openupgradelib.update_module_names`. Los UPDATE son
    no-op si el modulo no esta en la base, asi que no hace falta chequear la instalacion.
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
