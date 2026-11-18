import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Las escribe scripts/pre_odoo/180_190/070-backup_l10n_ar_stock_fields.py, del otro lado del
# pase. (tabla con los campos, columnas a reponer) -> la _bu es <tabla>_l10n_ar_stock_bu
RESTORE_FIELDS = [
    ("stock_lot", ["dispatch_number"]),
    ("stock_picking", ["dispatch_number", "cot", "cot_numero_unico", "cot_numero_comprobante"]),
    ("res_company", ["arba_cot"]),
    ("product_template", ["arba_code"]),
    ("uom_uom", ["arba_code"]),
]


def _restore_l10n_ar_stock_fields(cr):
    """Repone los campos de l10n_ar_stock que el pase borra al cambiar de módulo dueño.

    En 18 estos campos los declara l10n_ar_stock de Adhoc; en 19 ese nombre lo toma el módulo
    de Odoo (sin ellos) y el pase dropea las columnas con su dato, que l10n_ar_stock_ux recrea
    vacías. El valor viene del respaldo que deja
    scripts/pre_odoo/180_190/070-backup_l10n_ar_stock_fields.py.

    Corre en end-migration para quedar después de que l10n_ar_stock_ux (que depende de este
    módulo) recreó las columnas, y antes del copiado de la clave COT, que lee arba_cot. Solo
    completa el campo vacío: no pisa un dato cargado después del pase y es idempotente.
    """
    for table, columns in RESTORE_FIELDS:
        backup_table = "%s_l10n_ar_stock_bu" % table
        if not util.table_exists(cr, backup_table):
            continue
        for col in columns:
            if not util.column_exists(cr, table, col) or not util.column_exists(cr, backup_table, col):
                continue
            cr.execute(
                SQL(
                    "UPDATE %s t SET %s = bu.%s FROM %s bu WHERE bu.id = t.id AND COALESCE(t.%s, '') = ''",
                    SQL.identifier(table),
                    SQL.identifier(col),
                    SQL.identifier(col),
                    SQL.identifier(backup_table),
                    SQL.identifier(col),
                )
            )
            _logger.info("Repuesto %s.%s en %s filas", table, col, cr.rowcount)


def _copy_cot_key_to_parent(cr):
    """Pasa la clave COT de ARBA de la sucursal a su compañía padre cuando la padre no tiene.

    En 19 base/19.0.0.0/end-migration.py convierte compañías en sucursales y mueve a la
    padre los remitos y los tipos de operación, pero la clave COT (res.company.arba_cot)
    queda en la compañía donde estaba. "Obtener COT" usa la clave y el CUIT de la compañía
    del remito, así que sin esto falla con "Tiene que configurar COT de ARBA en la empresa
    <padre>" (ticket 128844, caso Odecon).

    Solo completa claves vacías y nunca pisa una que ya está. Si las sucursales de una misma
    padre tienen claves distintas, no elige: lo deja en el log.
    """
    if not util.column_exists(cr, "res_company", "arba_cot"):
        _logger.info("res_company.arba_cot does not exist, nothing to do")
        return

    cr.execute(
        SQL(
            """
            SELECT parent.id, parent.name, array_agg(DISTINCT branch.arba_cot)
              FROM res_company branch
              JOIN res_company parent ON parent.id = branch.parent_id
             WHERE COALESCE(branch.arba_cot, '') != ''
               AND COALESCE(parent.arba_cot, '') = ''
          GROUP BY parent.id, parent.name
            """
        )
    )
    for parent_id, parent_name, keys in cr.fetchall():
        if len(keys) > 1:
            _logger.warning(
                "Las sucursales de %s (%s) tienen %s claves COT distintas: no se copia ninguna",
                parent_name,
                parent_id,
                len(keys),
            )
            continue
        cr.execute(
            SQL(
                "UPDATE res_company SET arba_cot = %s WHERE id = %s AND COALESCE(arba_cot, '') = ''",
                keys[0],
                parent_id,
            )
        )
        _logger.info("Clave COT copiada a %s (%s) desde su sucursal", parent_name, parent_id)


def migrate(cr, version):
    _logger.info("Running end-migration of l10n_ar_stock for version %s", version)
    _restore_l10n_ar_stock_fields(cr)
    _copy_cot_key_to_parent(cr)
