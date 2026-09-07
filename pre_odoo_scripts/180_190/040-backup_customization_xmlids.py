import logging

_logger = logging.getLogger(__name__)

# Las lee pre_upgrade_scripts/180_190/fix_counted_customizations.py, del otro lado del pase.
XMLID_TABLE = "ir_model_data_personalizacion_bu"
EXISTING_TABLE = "registros_contados_bu"

# Los modelos que el contador de personalizaciones mira (wizard "Mi base",
# saas_client_adhoc/wizards/saas_client_dashboard.py). Solo respaldamos estos: el resto de
# ir_model_data no cambia lo que se le factura al cliente y engorda la tabla al pedo.
TABLE_BY_MODEL = {
    "ir.model": "ir_model",
    "ir.model.fields": "ir_model_fields",
    "ir.ui.view": "ir_ui_view",
    "ir.actions.server": "ir_act_server",
    "ir.cron": "ir_cron",
    "ir.actions.report": "ir_act_report_xml",
    "res.groups": "res_groups",
    "ir.rule": "ir_rule",
    "ir.model.access": "ir_model_access",
    "base.automation": "base_automation",
}
COUNTED_MODELS = tuple(TABLE_BY_MODEL)


def migrate(cr, version):
    """Respalda, antes del pase a Odoo, lo que hace falta para saber que se le cuenta al cliente.

    El contador de personalizaciones toma como personalizacion del cliente todo registro sin
    ir_model_data. Despues del pase aparecen contandose registros que no son del cliente, por
    dos motivos distintos, y ninguno de los dos se puede distinguir mirando solo la base nueva:

    1. Registros que EXISTIAN y perdieron su ir_model_data, porque Odoo fusiono o elimino el
       modulo que los declaraba. Para reponerlo hay que saber que XML ID tenian: XMLID_TABLE.
    2. Registros que NO EXISTIAN antes y los creo la migracion. Para reconocerlos hay que saber
       que ids habia antes: EXISTING_TABLE.

    Los dos datos solo existen de este lado del pase, por eso se respaldan aca.
    Motivo: tarea 72673, ticket 127277.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a proposito: esto corre sobre la base vieja, con
    el Odoo de la version de origen.
    """
    _logger.info("Backing up the customization XML IDs into %s", XMLID_TABLE)

    # Idempotente: el script puede correr mas de una vez sobre la misma base.
    cr.execute("DROP TABLE IF EXISTS %s" % XMLID_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT id, model, res_id, module, name, noupdate
              FROM ir_model_data
             WHERE model IN %%s
               AND res_id IS NOT NULL
        """
        % XMLID_TABLE,
        (COUNTED_MODELS,),
    )
    # Sin PK, el test_ensure_has_pk de Odoo la marca CRITICAL en cada corrida.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % XMLID_TABLE)
    cr.execute("CREATE INDEX ON %s (model, res_id)" % XMLID_TABLE)

    cr.execute("SELECT count(*) FROM %s" % XMLID_TABLE)
    _logger.info("Backed up %s customization XML IDs", cr.fetchone()[0])

    # Segundo respaldo: que registros EXISTIAN antes del pase. Sin esto, del otro lado no hay
    # forma de saber si un registro que hoy se cuenta como personalizacion es del cliente o lo
    # creo la migracion: los dos se ven igual, sin ir_model_data.
    _logger.info("Backing up the existing counted records into %s", EXISTING_TABLE)
    cr.execute("DROP TABLE IF EXISTS %s" % EXISTING_TABLE)
    cr.execute("CREATE TABLE %s (model varchar, res_id integer)" % EXISTING_TABLE)
    for model, table in TABLE_BY_MODEL.items():
        # La base vieja puede no tener la tabla (modulo no instalado): no es un error.
        cr.execute("SELECT to_regclass(%s)", (table,))
        if not cr.fetchone()[0]:
            continue
        cr.execute(
            "INSERT INTO %s (model, res_id) SELECT %%s, id FROM %s" % (EXISTING_TABLE, table),
            (model,),
        )
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (model, res_id)" % EXISTING_TABLE)

    cr.execute("SELECT count(*) FROM %s" % EXISTING_TABLE)
    _logger.info("Backed up %s existing counted records", cr.fetchone()[0])
