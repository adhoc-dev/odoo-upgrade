"""Drop the menu items the upgrade added to the websites.

Reads what scripts/pre_odoo/always/190-backup_website_menus.py backed up on the old
database. The navbar of each website has to end up with the same items it had: a menu whose
id is not in the backup is new and goes, unless it takes the place of a backed up item with
the same (website, name) that is no longer there -- that one is the same item recreated with
another id, not a new one.

Why they appear: the target version brings website.menu records the source one did not have
(`website_hr_recruitment.website_menu_jobs` in 18, `website_planning_field_service
.menu_service_requests` in 20), and website.menu.create duplicates a menu created without
website_id into every website. So the item comes back where the customer had removed it, and
is duplicated where they kept it.

The ir_model_data row of each menu goes with it: left behind, the next -u of its module
would find the xmlid pointing at nothing, create the menu again and duplicate it into every
website once more. Everything hanging from a dropped menu is dropped too (that is what the
foreign key does), and is in the list as well: an item that stays protects its ancestors.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "website_menu_bu"
# Upgrades to 19 still run the upgrade line 2684; same floor as the pre_odoo script.
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # applies it again, and a later -u of base in the same version does not.
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["website"]):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Not "no items": nobody looked. Dropping menus without the before picture would take
        # items the customer did have, so this goes to the request, not only to the log.
        log_message(
            cr,
            "No hay respaldo de los menus de los sitios web (%s): no se reviso el navbar, y puede "
            "haber quedado con items que sumo la actualizacion" % BACKUP_TABLE,
            "warning",
            module="website",
        )
        return

    cr.execute(SQL("SELECT id, website_id, name FROM %s", SQL.identifier(BACKUP_TABLE)))
    backup = cr.fetchall()
    cr.execute(
        SQL("SELECT id, website_id, name->>'en_US' FROM website_menu WHERE website_id IS NOT NULL ORDER BY id")
    )
    current = cr.fetchall()

    to_drop = _new_menus(backup, current)
    if not to_drop:
        _logger.info("No menu item was added to the websites")
        return

    to_drop, kept = _without_kept_subtree(cr, to_drop)
    if kept:
        log_message(
            cr,
            "Items que la actualizacion sumo pero que ahora tienen items del cliente abajo, se dejan: %s"
            % sorted(kept),
            "warning",
            module="website",
        )
    if not to_drop:
        _logger.info("Every menu item added by the upgrade holds items of the customer: none dropped")
        return

    try:
        with cr.savepoint():
            cr.execute(
                SQL("DELETE FROM ir_model_data WHERE model = 'website.menu' AND res_id IN %s", tuple(to_drop))
            )
            cr.execute(SQL("DELETE FROM website_menu WHERE id IN %s", tuple(to_drop)))
        _logger.info("Menu items added by the upgrade and dropped: %s", sorted(to_drop))
    except Exception as e:
        log_message(
            cr,
            "No se pudieron sacar los items que la actualizacion sumo al navbar (%s): %s"
            % (sorted(to_drop), str(e)[:300]),
            "warning",
            module="website",
        )


def _new_menus(backup, current):
    """Ids of ``current`` that are not in ``backup``, minus the ones that replace a lost item.

    The rescue has a quota per (website, name): as many as were backed up under that key and
    are no longer there by id. So a recreated item survives and a twin of a living one does
    not. The backup holds every menu, so one that changed website_id is still known by its id.
    """
    current_ids = {row[0] for row in current}
    quota = {}
    for menu_id, website_id, name in backup:
        if website_id is None:
            continue
        key = (website_id, name)
        quota[key] = quota.get(key, 0) + (0 if menu_id in current_ids else 1)

    backup_ids = {row[0] for row in backup}
    new_menus = set()
    for menu_id, website_id, name in current:
        if menu_id in backup_ids:
            continue
        key = (website_id, name)
        if quota.get(key):
            quota[key] -= 1
            continue
        new_menus.add(menu_id)
    return new_menus


def _without_kept_subtree(cr, to_drop):
    """Split ``to_drop`` into what can go and what holds items of the customer below it.

    parent_id cascades on delete, so an ancestor has to be spared when ANY of its descendants
    is kept, not only when its direct child is.
    """
    cr.execute(SQL("SELECT id, parent_id FROM website_menu"))
    parent_of = dict(cr.fetchall())

    kept = set()
    for menu_id in parent_of:
        if menu_id in to_drop:
            continue
        seen = set()
        ancestor = parent_of.get(menu_id)
        while ancestor and ancestor not in seen:
            seen.add(ancestor)
            if ancestor in to_drop:
                kept.add(ancestor)
            ancestor = parent_of.get(ancestor)
    return to_drop - kept, kept
