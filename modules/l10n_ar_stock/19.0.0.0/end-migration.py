import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Pasa la clave COT de ARBA de la sucursal a su compañía padre cuando la padre no tiene.

    En 19 base/19.0.0.0/end-migration.py convierte compañías en sucursales y mueve a la
    padre los remitos y los tipos de operación, pero la clave COT (res.company.arba_cot)
    queda en la compañía donde estaba. "Obtener COT" usa la clave y el CUIT de la compañía
    del remito, así que sin esto falla con "Tiene que configurar COT de ARBA en la empresa
    <padre>" (ticket 128844, caso Odecon).

    Corre en end-migration para quedar después del end de base, que es el que arma las
    sucursales. Solo completa claves vacías y nunca pisa una que ya está. Si las sucursales
    de una misma padre tienen claves distintas, no elige: lo deja en el log.
    """
    _logger.info("Running end-migration of l10n_ar_stock for version %s", version)

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
