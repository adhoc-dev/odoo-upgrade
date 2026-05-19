import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running post-migrate script for l10n_uy_edi")
    env = util.env(cr)

    cron_values = {
        "name": "UY: Create vendor bills (sync from Uruware)",
        "interval_number": 1,
        "interval_type": "hours",
        "model_id": env.ref("l10n_uy_edi.model_l10n_uy_edi_document").id,
        "state": "code",
        "code": "model.cron_l10n_uy_edi_get_vendor_bills()",
        "active": True,
    }

    cron_vendor_bills_received = env.ref(
        "l10n_uy_edi.ir_cron_get_vendor_bills_received", raise_if_not_found=False
    )
    if cron_vendor_bills_received:
        cron_vendor_bills_received.write(cron_values)
        return

    cron_vendor_bills_received = env["ir.cron"].create(cron_values)
    env["ir.model.data"].create(
        {
            "module": "l10n_uy_edi",
            "name": "ir_cron_get_vendor_bills_received",
            "model": "ir.cron",
            "res_id": cron_vendor_bills_received.id,
            "noupdate": True,
        }
    )
