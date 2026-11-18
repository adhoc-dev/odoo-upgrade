import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Campos que en 18 declara l10n_ar_stock de Adhoc sobre modelos de Odoo y que en 19 pasan a
# l10n_ar_stock_ux. En el salto, el módulo l10n_ar_stock pasa a ser el de Odoo (que no los
# tiene) y el pase da esas columnas por obsoletas y las borra con su dato; l10n_ar_stock_ux las
# vuelve a declarar y las recrea vacías. Se respaldan acá y se reponen del otro lado del pase
# en modules/l10n_ar_stock/19.0.0.0/end-migration.py.
# (tabla de origen, columnas) -> una _bu por tabla: <tabla>_l10n_ar_stock_bu
BACKUP_FIELDS = [
    ("stock_lot", ["dispatch_number"]),
    ("stock_picking", ["dispatch_number", "cot", "cot_numero_unico", "cot_numero_comprobante"]),
    ("res_company", ["arba_cot"]),
    ("product_template", ["arba_code"]),
    ("uom_uom", ["arba_code"]),
]
# Único salto donde estos campos cambian de módulo dueño. La carpeta 180_190 ya lo acota; el
# rango se declara igual para que el gate tenga la misma forma que el resto de los pre-odoo.
TARGET_VERSION = 19


def _existing_columns(cr, table, columns):
    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name = ANY(%s)",
        (table, columns),
    )
    present = {row[0] for row in cr.fetchall()}
    return [c for c in columns if c in present]


def migrate(cr, version):
    """Respalda los campos de l10n_ar_stock que cambian de módulo dueño antes de que el pase
    borre sus columnas. El valor se repone del otro lado del pase desde estas _bu.

    El gate es la existencia de cada columna, no el módulo: según cómo haya llegado la base a
    18 nuestro módulo puede llamarse l10n_ar_stock o l10n_ar_stock_custom, pero el dato a
    respaldar es la columna, exista quien exista el módulo que la declara.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a propósito: esto corre sobre la base vieja,
    con el Odoo de la versión de origen. Las tablas y columnas se interpolan porque son
    constantes del módulo (BACKUP_FIELDS), nunca datos de la base.
    """
    for table, columns in BACKUP_FIELDS:
        backup_table = "%s_l10n_ar_stock_bu" % table
        # Borra la _bu antes del gate: una tabla de una corrida anterior no puede viajar en un
        # request al que el script no aplica.
        if not should_back_up(cr, backup_table, first_target=TARGET_VERSION, last_target=TARGET_VERSION):
            continue
        cols = _existing_columns(cr, table, columns)
        if not cols:
            _logger.info("%s no tiene ninguna de %s, nada que respaldar", table, columns)
            continue
        cols_sql = ", ".join(cols)
        where = " OR ".join("COALESCE(%s, '') != ''" % col for col in cols)
        query = "SELECT id, %s FROM %s WHERE %s" % (cols_sql, table, where)
        backed_up = create_backup(cr, backup_table, query)
        _logger.info("Respaldados %s registros de %s (%s) en %s", backed_up, table, cols_sql, backup_table)
