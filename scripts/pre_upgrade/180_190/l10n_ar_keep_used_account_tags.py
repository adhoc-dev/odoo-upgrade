import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Tags contables que eliminó ingadhoc/odoo-argentina@63d2dd6. Los que todavía estén
# en uso los desvinculamos de su módulo para que el `-u` no los borre con él.
TAG_XMLIDS = [
    "l10n_ar_ux.tag_a_cuenta_ganancias",
    "l10n_ar_ux.tag_a_cuenta_iva",
    "l10n_ar_ux.tag_iva_primer_parrafo",
    "l10n_ar_ux.tag_unaffected_earnings",
    "l10n_ar_ux.tag_impuestos_a_las_ganancias",
    "l10n_ar_ux.tag_liquidacion_de_iva",
    "l10n_ar_ux.tag_liquidacion_de_iibb",
    "l10n_ar_ux.tag_liquidacion_de_ganancias",
    "l10n_ar_ux.tag_liquidacion_sicore_aplicado",
    "l10n_ar_ux.tag_liquidacion_iibb_aplicado",
    "l10n_ar_ux.tax_tag_a_cuenta_suss",
    "l10n_ar_ux.tax_tag_a_cuenta_iibb",
    "l10n_ar_ux.tax_tag_a_cuenta_ganancias",
    "l10n_ar_ux.tax_tag_a_cuenta_iva",
    "l10n_ar_ux.tag_ret_perc_iibb_aplicada",
    "l10n_ar_ux.tag_ret_perc_sicore_aplicada",
    "l10n_ar_account_reports.ar_esp_capital",
    "l10n_ar_account_reports.ar_esp_reservas",
    "l10n_ar_account_reports.ar_esp_resultados",
    "l10n_ar_account_reports.ar_esp_resultado_del_ejercicio",
]

# Tablas y columnas con foreign key a account_account_tag: por ahí se ve si el tag
# quedó en uso.
RELATED_COLUMNS_QUERY = """
    SELECT c.relname, a.attname
      FROM pg_catalog.pg_constraint con
      JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
      JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid
                                    AND a.attnum = ANY(con.conkey)
      JOIN pg_catalog.pg_class cr ON cr.oid = con.confrelid
      JOIN pg_catalog.pg_attribute ar ON ar.attrelid = con.confrelid
                                     AND ar.attnum = ANY(con.confkey)
     WHERE con.contype = 'f'
       AND cr.relname = 'account_account_tag'
       AND ar.attname = 'id'
"""


def migrate(cr, version):
    """Protege los tags contables eliminados en 19 que la base todavía usa.

    Migrado desde la upgrade line 2143 ("Pre Adhoc de cuentas eliminadas en 19"),
    que resolvía los xmlids contra la base old por RPC. Acá se resuelven contra
    `ir_model_data` de la propia base: los ids se preservan en el upgrade y el
    registro tiene que estar, es el mismo que se borra más abajo.

    Borrar el `ir_model_data` desvincula el tag de su módulo sin tocar el tag: al
    actualizar el módulo, Odoo ya no lo ve como suyo y lo deja donde está, con lo
    que los reportes históricos siguen cuadrando.

    Es idempotente: en la segunda corrida los xmlids ya no están.
    """
    _logger.info("Running 'l10n_ar_keep_used_account_tags.py' script for version %s", version)

    if not util.module_installed(cr, "l10n_ar_tax"):
        _logger.info("l10n_ar_tax is not installed, nothing to do")
        return

    cr.execute(
        SQL(
            "SELECT id, res_id FROM ir_model_data WHERE model = 'account.account.tag' AND (module, name) IN %(keys)s",
            keys=tuple(tuple(xmlid.split(".")) for xmlid in TAG_XMLIDS),
        )
    )
    tag_by_data_id = dict(cr.fetchall())
    if not tag_by_data_id:
        _logger.info("None of the removed tags is present in this database")
        return

    cr.execute(SQL(RELATED_COLUMNS_QUERY))
    related_columns = cr.fetchall()
    if not related_columns:
        return

    tag_ids = tuple(tag_by_data_id.values())
    used_query = SQL(" UNION ").join(
        [
            SQL(
                "SELECT %s FROM %s WHERE %s IN %s",
                SQL.identifier(column),
                SQL.identifier(table),
                SQL.identifier(column),
                tag_ids,
            )
            for table, column in related_columns
        ]
    )
    cr.execute(used_query)
    used_tag_ids = {row[0] for row in cr.fetchall()}

    data_ids = tuple(data_id for data_id, tag_id in tag_by_data_id.items() if tag_id in used_tag_ids)
    if not data_ids:
        _logger.info("None of the removed tags is in use, leaving them to the module update")
        return

    cr.execute(SQL("DELETE FROM ir_model_data WHERE id IN %s", data_ids))
    _logger.info("Unlinked %s account tags still in use from their module", len(data_ids))
