import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Países donde opera Mercado Pago.
COUNTRY_CODES = (
    "AR", "BO", "BR", "CL", "CO", "CR", "DO", "EC", "GT", "HN",
    "MX", "NI", "PA", "PY", "PE", "SV", "UY", "VE",
)


def migrate(cr, version):
    """Completa el país de los proveedores de pago Mercado Pago que quedan sin país.

    Migrado desde la upgrade line 2464 ("Actualizar país en mercado pago 19"), que
    hacía el mismo UPDATE por RPC. El país se toma de la compañía del proveedor y
    solo se completa si quedó vacío; de paso se apaga `allow_tokenization`, que en
    19 no acompaña a este proveedor.

    Es idempotente: los proveedores que ya tienen país no se vuelven a tocar.
    """
    _logger.info("Running 'payment_mercado_pago_account_country.py' script for version %s", version)

    if not util.column_exists(cr, "payment_provider", "mercado_pago_account_country_id"):
        _logger.info("payment_mercado_pago is not installed, nothing to do")
        return

    cr.execute(
        SQL(
            """
            UPDATE payment_provider pp
               SET mercado_pago_account_country_id = rp.country_id,
                   allow_tokenization = false
              FROM res_company rc
              JOIN res_partner rp ON rp.id = rc.partner_id
              JOIN res_country country ON country.id = rp.country_id
             WHERE pp.company_id = rc.id
               AND pp.code = 'mercado_pago'
               AND pp.mercado_pago_account_country_id IS NULL
               AND country.code IN %(country_codes)s
            """,
            country_codes=COUNTRY_CODES,
        )
    )
    _logger.info("Set the account country on %s mercado pago payment providers", cr.rowcount)
