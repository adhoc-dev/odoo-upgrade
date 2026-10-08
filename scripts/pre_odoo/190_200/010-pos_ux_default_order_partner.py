import logging

_logger = logging.getLogger(__name__)

# pos_ux agrega pos.config.default_partner_id: el cliente que viene pre-seleccionado en cada
# pedido nuevo (el "Consumidor Final" de una caja B2C). En 20.0 Odoo suma un campo del core con
# ESE nombre y otro significado —el partner contra el que se arma el asiento de cierre de la
# sesion, requerido y con default propio— dentro del rediseno contable del POS (commit
# f1f5a0b8f8a3). El modulo migrado renombra el suyo a default_order_partner_id, pero la columna
# de la base es una sola: si Odoo corre su upgrade viendola, el valor de pos_ux queda leido como
# partner de cierre y el campo nuevo del modulo nace vacio. Renombrarla antes del pase es lo que
# separa las dos cosas: Odoo no la ve, crea su default_partner_id de cero, y el valor viejo llega
# intacto al campo nuevo.
#
# El campo espejo de ajustes (res.config.settings.pos_default_partner_id) no se toca: es
# transient, no tiene data, y en 20.0 lo declara el core. Su registro viejo a nombre de pos_ux lo
# limpia nuestro -u all al actualizar el modulo.

OLD_COLUMN = "default_partner_id"
NEW_COLUMN = "default_order_partner_id"


def migrate(cr, version):
    """Renombra pos_config.default_partner_id antes de que el campo del core tome el nombre.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a proposito: esto corre sobre la base vieja,
    con el Odoo de la version de origen.
    """
    # El gate va aca: la plataforma no filtra por modulo.
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = %s AND state = 'installed'", ("pos_ux",))
    if not cr.fetchone():
        return

    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'pos_config' AND column_name IN %s",
        ((OLD_COLUMN, NEW_COLUMN),),
    )
    columns = {row[0] for row in cr.fetchall()}
    # Idempotente: el script puede correr mas de una vez.
    if NEW_COLUMN in columns or OLD_COLUMN not in columns:
        _logger.info("Nothing to rename on pos_config (columns found: %s)", ", ".join(sorted(columns)) or "none")
        return

    _logger.info("Renaming pos_config.%s to %s before the pass", OLD_COLUMN, NEW_COLUMN)
    cr.execute("ALTER TABLE pos_config RENAME COLUMN %s TO %s" % (OLD_COLUMN, NEW_COLUMN))
    cr.execute(
        "UPDATE ir_model_fields SET name = %s WHERE model = 'pos.config' AND name = %s",
        (NEW_COLUMN, OLD_COLUMN),
    )
    # El xmlid del campo sigue la convencion del ORM, la misma que usa odoo.upgrade.util.
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s
         WHERE model = 'ir.model.fields'
           AND module = 'pos_ux'
           AND name = %s
        """,
        ("field_pos_config__%s" % NEW_COLUMN, "field_pos_config__%s" % OLD_COLUMN),
    )
