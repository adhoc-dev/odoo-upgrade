import logging

_logger = logging.getLogger(__name__)

# La lee pre_upgrade_scripts/180_190/hr_contract_orphan_group.py, del otro lado del upgrade.
BACKUP_TABLE = "res_groups_xmlid_bu"


def migrate(cr, version):
    """Guarda el xmlid de cada grupo antes de mandar la base a Odoo.

    Odoo fusiona módulos durante su upgrade y algunos grupos vuelven vivos pero sin
    xmlid, que es como el contador de personalizaciones los factura. Del otro lado no
    queda nada que los identifique, así que el dato tiene que viajar desde acá.

    Sin `odoo.tools.SQL` ni `odoo.upgrade.util` a propósito: esto corre sobre la base
    vieja, con el Odoo de la versión de origen.
    """
    _logger.info("Backing up the group xmlids into %s", BACKUP_TABLE)

    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT DISTINCT ON (d.res_id)
                   d.res_id AS group_id,
                   d.module AS module,
                   d.name AS name,
                   g.create_date AS create_date
              FROM ir_model_data d
              JOIN res_groups g ON g.id = d.res_id
             WHERE d.model = 'res.groups'
             ORDER BY d.res_id, d.id
        """
        % BACKUP_TABLE
    )
    # Sin PK, el test_ensure_has_pk de Odoo la marca CRITICAL en cada corrida. El
    # DISTINCT ON ya garantiza una sola fila por grupo.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (group_id)" % BACKUP_TABLE)
