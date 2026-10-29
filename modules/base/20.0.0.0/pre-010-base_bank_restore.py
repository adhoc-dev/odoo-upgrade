import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Backed up by scripts/pre_odoo/190_200/020-backup_res_bank.py.
BANK_TABLE = "res_bank_bu"


def migrate(cr, version):
    """Run the scripts of base_bank when it is installed in this upgrade.

    base_bank is new in 20: it comes as a dependency of l10n_latam_check_ux or l10n_ar_bank, and Odoo
    does not run the scripts of a module that is being installed. Its post-migration restores the
    banks that Odoo 20 removed from base. It only applies when base_bank is marked to install: this
    does not install it.
    """
    if not util.table_exists(cr, BANK_TABLE):
        return
    _logger.info("Running the upgrade scripts of base_bank, if it is installed, to restore the banks")
    util.force_upgrade_of_fresh_module(cr, "base_bank")
