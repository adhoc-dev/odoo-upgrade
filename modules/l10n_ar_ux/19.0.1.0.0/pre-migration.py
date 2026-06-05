import logging

from odoo.upgrade import util
from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

# Backup de la tabla vieja antes de que se carguen los nuevos datos
_backup_table = ("afip_activity", "afip_activity_bu")

# Columnas a copiar en las tablas que referencian la actividad
_column_copy = {
    "account_account": [
        ("l10n_ar_afip_activity_id", "l10n_ar_afip_activity_id_bu", None),
    ],
    "res_company": [
        ("l10n_ar_afip_activity_id", "l10n_ar_afip_activity_id_bu", None),
    ],
}

def _xmlid_lookup(cr, xmlid: str) -> tuple[str, int]:
    """copy off Low level xmlid lookup
    Return (res_model, res_id)
    """
    module, name = xmlid.split('.', 1)
    query = "SELECT model, res_id FROM ir_model_data WHERE module=%s AND name=%s"
    cr.execute(query, [module, name])
    result = cr.fetchone()
    return result

def migrate(cr, version):
    """Hacemos back up de los datos de actividad antiguos y preparamos para la carga de nuevos datos.

    Idempotente: en un re-run del -u la columna vieja puede no existir (Odoo la
    dropea al terminar la carga) o el backup puede estar hecho; en ambos casos
    se saltea sin fallar.
    """

    # Crear backup de la tabla vieja antes de cargar los nuevos datos
    old_table, backup_table = _backup_table
    if not util.table_exists(cr, old_table):
        _logger.info("Table %s does not exist, skipping backup", old_table)
    elif util.table_exists(cr, backup_table):
        _logger.info("Backup table %s already exists, skipping", backup_table)
    else:
        _logger.info("Creando tabla de respaldo %s a partir de %s", backup_table, old_table)
        cr.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM {old_table}")

    # Copiar columnas viejas a columnas de backup en tablas referenciadas
    column_copy = {}
    for table, specs in _column_copy.items():
        pending = []
        for old, new, field_type in specs:
            if not util.column_exists(cr, table, old):
                _logger.info("Column %s.%s does not exist, skipping backup", table, old)
            elif util.column_exists(cr, table, new):
                _logger.info("Backup column %s.%s already exists, skipping", table, new)
            else:
                pending.append((old, new, field_type))
        if pending:
            column_copy[table] = pending

    if column_copy:
        _logger.info("Copiando columnas de las columnas viejas a las columnas de respaldo")
        openupgrade.copy_columns(cr, column_copy)


    xml_id_names = [
        "tag_a_cuenta_ganancias",
        "tag_a_cuenta_iva",
        "tag_iva_primer_parrafo",
        "tag_unaffected_earnings",
        "tag_impuestos_a_las_ganancias",
        "tag_liquidacion_de_iva",
        "tag_liquidacion_de_iibb",
        "tag_liquidacion_de_ganancias",
        "tag_liquidacion_sicore_aplicado",
        "tag_liquidacion_iibb_aplicado",
        "tax_tag_a_cuenta_suss",
        "tax_tag_a_cuenta_iibb",
        "tax_tag_a_cuenta_ganancias",
        "tax_tag_a_cuenta_iva",
        "tag_ret_perc_iibb_aplicada",
        "tag_ret_perc_sicore_aplicada",
    ]
    for xml_id_name in xml_id_names:
        account_tag_id = _xmlid_lookup(cr, f"l10n_ar_ux.{xml_id_name}")
        if account_tag_id:
            cr.execute(
                """
                SELECT 1
                FROM account_account_tag_account_tax_repartition_line_rel
                WHERE account_account_tag_id = %s
                LIMIT 1
            """,
                (account_tag_id[1],),
            )
            used_in_taxes = cr.fetchone()
            if used_in_taxes:
                _logger.info(f"Eliminamos el extenal ref l10n_ar_ux.{xml_id_name} ya que se encuentra en uso")
                cr.execute(
                    """
                    DELETE FROM ir_model_data
                    WHERE module = 'l10n_ar_ux' AND name = %s
                """,
                    (xml_id_name,),
                )

    _logger.info("Pre-migración completada exitosamente")
