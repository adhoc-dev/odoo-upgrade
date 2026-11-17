import logging

from oba import log_message, should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Modulos nuestros que tienen un homonimo en Odoo: l10n_ar_stock desde 19.0 y
# l10n_uy_edi_stock ya desde 18.0 (en 19.0 los nuestros se renombraron a `_ux`). Si la base
# llega a Odoo con el nombre real, su plataforma actualiza el registro como si fuera el suyo
# y nuestras vistas quedan referenciando campos que el modulo de Odoo no define. Renombrados
# no los conoce y los deja intactos; el nombre real se repone del otro lado, en
# scripts/pre_upgrade/180_190/module_changes.json. Una base que paso de 17 a 18 por Odoo ya
# trae el nuestro renombrado a `_custom`, y la fila con el nombre real es la del modulo de Odoo.
MODULE_RENAMES = [
    ("l10n_ar_stock", "l10n_ar_stock_custom"),
    ("l10n_uy_edi_stock", "l10n_uy_edi_stock_custom"),
]


def migrate(cr, version):
    """Renombra los modulos de MODULE_RENAMES en la base vieja, antes del dump a Odoo.

    Equivalente en SQL del rename de `openupgradelib.update_module_names`. Los UPDATE son
    no-op si el modulo no esta en la base, asi que no hace falta chequear la instalacion.
    """
    # Only on the first hop: a base that already went through Odoo comes back renamed
    if not should_run_pre_odoo(cr, first_target=19, last_target=19, position="first"):
        return
    for old, new in MODULE_RENAMES:
        # Odoo already renamed ours on an earlier hop: the real-name row is its own module
        cr.execute("SELECT 1 FROM ir_module_module WHERE name = %s", (new,))
        if cr.fetchone():
            cr.execute("SELECT 1 FROM ir_module_module WHERE name = %s AND state = 'installed'", (old,))
            if cr.fetchone():
                log_message(
                    cr,
                    "%s ya existe y %s está instalado: no se renombró. Revisar si %s es el de Odoo o el nuestro."
                    % (new, old, old),
                    "warning",
                    module=old,
                )
            else:
                _logger.info("Module %s already exists, %s is left as is", new, old)
            continue
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
