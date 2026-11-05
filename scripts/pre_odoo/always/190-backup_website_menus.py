import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-190-drop_new_website_menus.py, on the other side of the upgrade.
BACKUP_TABLE = "website_menu_bu"
# Upgrades to 19 still run the upgrade line 2684; same floor as the consumer.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    """Back up the menus of the websites before the database is sent to Odoo.

    The target version brings website.menu records the source one did not have, and a menu
    created without website_id is duplicated into every website: the items the customer had
    removed come back, and the ones they kept get a twin. The consumer on the other side
    drops what is not in here.

    Every menu is taken, not only the ones of a website: a menu that changes website_id in
    the upgrade still has to be recognised by its id. `url` is not taken, it stops being a
    column in 20; neither is parent_id, the consumer reads the tree of the new database.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE first, so a table left by an earlier run does not reach a request
    # that skips. The pre-odoo runs on the whole database: the module is checked here.
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, modules=["website"]):
        return

    # A jump to 20 comes from 19, where the name is already jsonb (translatable fields became
    # jsonb in 16). If an older source ever reaches here, skip instead of breaking the
    # customer's run on `->>`.
    cr.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = 'website_menu' AND column_name = 'name' AND data_type = 'jsonb'"
    )
    if not cr.fetchone():
        _logger.warning("website_menu.name is not jsonb: the website menus are not backed up")
        return

    _logger.info("Backing up the website menus into %s", BACKUP_TABLE)

    rows = create_backup(
        cr,
        BACKUP_TABLE,
        """
        SELECT id, website_id, name->>'en_US' AS name
          FROM website_menu
        """,
    )
    _logger.info("%s menus backed up", rows)
