import logging
import re

from oba import request_context

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
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Upgrades to 19 still run the upgrade line. The target comes in the request context; a
    # provider that does not send it only upgrades to 19. Outside a provider run it backs up.
    context = request_context(cr)
    target = re.search(r"\d+", context.get("to_version") or "")
    if context and (not target or int(target.group()) < FIRST_TARGET_VERSION):
        _logger.info("Not an upgrade to %s or later: the upgrade line handles it", FIRST_TARGET_VERSION)
        return

    # Only with these modules installed, like the upgrade line.
    cr.execute(
        "SELECT count(*) FROM ir_module_module WHERE name IN %s AND state = 'installed'",
        (MODULES,),
    )
    if cr.fetchone()[0] != len(MODULES):
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

    cr.execute("CREATE TABLE %s AS SELECT a.id FROM ir_actions a WHERE %s" % (BACKUP_TABLE, condition), (OLD_NAMES,))
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
