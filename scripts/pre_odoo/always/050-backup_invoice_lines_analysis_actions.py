import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-050-repoint_invoice_lines_analysis_action.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_actions_invoice_lines_analysis_bu"
# Upgrades to 19 still run the upgrade line; same floor as the consumer.
FIRST_TARGET_VERSION = 20
MODULES = ("spreadsheet_dashboard", "l10n_ar_ux")
OLD_NAMES = ("Invoice Lines Analysis", "Analisis de Lineas de Facturas")


def migrate(cr, version):
    """Back up the ids of the "Invoice Lines Analysis" actions before the database is sent to Odoo.

    Custom dashboards point to them by id, and in 18.0 the action becomes "Invoices Analysis".
    The upgrade line it replaces read the
    ids from the old database to repoint the dashboards.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. Upgrades to 19 still run the upgrade line.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=MODULES):
        return

    _logger.info("Backing up the ids of the Invoice Lines Analysis actions into %s", BACKUP_TABLE)

    cr.execute(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 'ir_actions' AND column_name = 'name'"
    )
    if cr.fetchone()[0] == "jsonb":
        # Translatable since 16.0: any of its translations counts, like the RPC search did.
        condition = "EXISTS (SELECT 1 FROM jsonb_each_text(a.name) t WHERE t.value IN %s)"
    else:
        condition = "a.name IN %s"

    create_backup(cr, BACKUP_TABLE, "SELECT a.id FROM ir_actions a WHERE %s" % condition, (OLD_NAMES,))
