import logging

_logger = logging.getLogger(__name__)


def migrate(env):
    """Changes the SII send cron of l10n_cl_edi to every 4 hours, as a client could have done.

    The pre_odoo script backs it up only when it differs from the default of 19 (once a day),
    and the end-migration of saas_client_l10n_cl takes it to the cron of l10n_cl_edi_fix_send_dte.
    """
    cron = env.ref("l10n_cl_edi.ir_cron_send_send", raise_if_not_found=False)
    if not cron:
        return
    cron.write({"interval_number": 4, "interval_type": "hours"})
    _logger.info("Set the SII send cron of l10n_cl_edi to every 4 hours")
