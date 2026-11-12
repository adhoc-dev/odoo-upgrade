import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-190-restore_website_custom_views.py, on the other side of the upgrade.
BACKUP_TABLE = "ir_ui_view_website_custom_bu"
# Upgrades to 19 still run the upgrade line 2490; same floor as the consumer.
FIRST_TARGET_VERSION = 20
# The generic view is kept under website 0: a primary key takes no NULL, and the shop
# wishlist option falls back to the generic view when a website has no copy of its own.
GENERIC_WEBSITE_ID = 0
# In 20 this view is gone and only the CSS class is left, so its old state is readable here only.
WISHLIST_KEY = "website_sale_wishlist.add_to_wishlist"


def migrate(cr, version):
    """Back up the state of the website views before the database is sent to Odoo.

    On the other side, end-180 deactivates every customized website view and renames its
    key, so after it nothing tells which ones the customer had on. end-190 puts that state
    back and reads it from here.

    By key and website, because end-080 copies views and one of the new database can have an
    id that never existed here. The id goes along as a fallback: the upgrade also renames
    keys, and then the key is the half that does not match.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Upgrades to 19 still run the upgrade line, and only the last jump deprecates, which is
    # where the consumer reads this: same position, so the table is written on the jump that
    # uses it.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["website"], position="last"):
        return

    _logger.info("Backing up the state of the website views into %s", BACKUP_TABLE)
    # DISTINCT ON because a dirty database can hold more than one view per key and website,
    # and the primary key takes one: the same one end-080 takes, by priority and id.
    # coalesce on active because the column is nullable: the consumer reads NULL as "this view
    # was not on the old database" and would leave the view deprecated.
    create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT DISTINCT ON (key, coalesce(website_id, %s))
               id, key, coalesce(website_id, %s) AS website_id, coalesce(active, true) AS active
          FROM ir_ui_view
         WHERE type = 'qweb'
           AND key IS NOT NULL
           AND (website_id IS NOT NULL OR key = %s)
         ORDER BY key, coalesce(website_id, %s), priority, id
        """,
        (GENERIC_WEBSITE_ID, GENERIC_WEBSITE_ID, WISHLIST_KEY, GENERIC_WEBSITE_ID),
        primary_key=("key", "website_id"),
    )
