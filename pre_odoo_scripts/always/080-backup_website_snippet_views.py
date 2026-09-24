import logging

_logger = logging.getLogger(__name__)

# Read by base/0.0.0/end-restore_website_snippet_views.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_ui_view_website_snippet_bu"
# Their keys change from version to version, so they are not in the deprecated-keys list.
TARGET_KEYS = (
    "portal.user_sign_in",
    "website_sale.option_collapse_products_categories",
    "website_sale.products_attributes",
    "website_sale.filter_products_price",
    "website_sale.filter_products_tags",
    "website_sale.products_attributes_collapsible",
    "website_sale.products_add_to_cart",
    "website_sale_comparison.add_to_compare",
    "website_sale_wishlist.add_to_wishlist",
)


def migrate(cr, version):
    """Back up the website copies of some shop and login views before the database is sent to Odoo.

    The upgrade can drop those copies or change their state. The upgrade line it replaces read them from the old database to bring back,
    for each website, the copy with the state it had.

    By key and website, not by id: the copy may not survive the upgrade. The id-based part,
    re-activating what Odoo disabled, is done by 010-backup_active_views.py.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # First: a table left by an earlier run must not reach a request that skips.
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)

    # Only with website installed, like the upgrade line; the version gate is in the consumer.
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'website' AND state = 'installed'")
    if not cr.fetchone():
        return

    _logger.info("Backing up the website copies of the snippet views into %s", BACKUP_TABLE)

    # One copy per key and website, as the upgrade line took with its limit=1.
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT DISTINCT ON (key, website_id) key, website_id, active
              FROM ir_ui_view
             WHERE key IN %%s
               AND website_id IS NOT NULL
             ORDER BY key, website_id, priority, id
        """
        % BACKUP_TABLE,
        (TARGET_KEYS,),
    )
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (key, website_id)" % BACKUP_TABLE)
