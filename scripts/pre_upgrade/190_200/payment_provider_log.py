import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Every provider here extends payment.transaction, which is where the log hooks in
PROVIDERS = [
    "payment_abitab",
    "payment_mercado_pago_ux",
    "payment_pay_way",
    "payment_redpagos",
    "payment_sistarbanc",
]


def migrate(cr, version):
    installed = [provider for provider in PROVIDERS if util.module_installed(cr, provider)]
    if not installed:
        return

    _logger.info("Installing payment_provider_log, installed providers: %s", ", ".join(installed))
    util.force_install_module(cr, "payment_provider_log")
