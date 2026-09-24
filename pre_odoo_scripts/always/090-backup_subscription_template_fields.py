import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-restore_subscription_plan_fields.py, on the other side of the upgrade.
BACKUP_TABLE = "sale_order_template_subscription_bu"
COLUMNS = ("recurrence_id", "dates_required", "add_period_dates_to_description", "invoicing_method")


def migrate(cr, version):
    """Back up the sale_subscription_ux fields of the recurring templates before the database is sent to Odoo.

    In 17.0 the recurring sale.order.template becomes a sale.subscription.plan with the same
    id. The upgrade line it replaces read those fields from
    the old database to write them on the plan.

    Gated by the columns and not by the version: they only exist while the template is still
    the recurring one.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'sale_subscription_ux' AND state = 'installed'")
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT count(*)
          FROM information_schema.columns
         WHERE table_name = 'sale_order_template'
           AND column_name IN %s
        """,
        (COLUMNS,),
    )
    if cr.fetchone()[0] != len(COLUMNS):
        _logger.info("sale_order_template has no recurring fields to back up")
        return

    _logger.info("Backing up the recurring fields of the sale order templates into %s", BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT id, dates_required, add_period_dates_to_description, invoicing_method
              FROM sale_order_template
             WHERE recurrence_id IS NOT NULL
        """
        % BACKUP_TABLE
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (id)" % BACKUP_TABLE)
