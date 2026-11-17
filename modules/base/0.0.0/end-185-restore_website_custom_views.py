"""Put back, per website, the state each customized view had before the upgrade.

end-180 deactivates every customized website view and appends ``_depreciada`` to its key, so
the website takes the standard ones. A view the customer had on has to come back on; one that
was off keeps its own key and stays archived, because with the key renamed it stops overriding
the generic view and the new version turns that option back on by default.

Reads what scripts/pre_odoo/always/185-backup_website_custom_views.py backed up on the old
database, by key and website: end-080 copies views, so an id of the new database may never
have existed on the old one.

Ported from upgrade line 2490, which did this over RPC up to 19. Two things change inside the
``-u`` and both are handled here:

- Its gate was an HTTP GET, and no server is serving this database. ``oba.render_website``
  renders the same pages through the real router with no server, which is the only check that
  catches what breaks only at render time. The ORM's own gate is not an option: a write
  validates through ``_check_xml``, and ``pre-0-disable-check-views.py`` leaves that a no-op
  for the whole ``-u`` without restoring it. A view is turned back on inside a savepoint, and
  if the website stops rendering it goes back to where it was.
- Writing by SQL, like end-180: ``ir.ui.view.write`` unlinks every ``ir.ui.view.custom``
  pointing at the view, which is not ours to drop.

A website that already fails to render before all this is left alone: turning a view back on
there proves nothing, and the failure would look like ours.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import RENDER_OK, log_message, render_website, should_run

_logger = logging.getLogger(__name__)

# Written by scripts/pre_odoo/always/185-backup_website_custom_views.py on the old database.
BACKUP_TABLE = "ir_ui_view_website_custom_bu"
# Upgrades to 19 still run the upgrade line 2490; same floor as end-180.
FIRST_TARGET_VERSION = 20
SUFFIX = "_depreciada"
# The generic view is backed up under website 0, as the pre_odoo half explains.
GENERIC_WEBSITE_ID = 0
WISHLIST_KEY = "website_sale_wishlist.add_to_wishlist"
# In 20 the website_sale_wishlist addon is gone: the option is these two classes of
# website_sale, both of them in the default of shop_opt_products_design_classes.
WISHLIST_CLASSES = ("o_wsale_products_opt_has_wishlist", "o_wsale_products_opt_wishlist_fixed")


def _old_state(cr):
    """What each view looked like on the old database, indexed by (key, website) and by id.

    Two indexes because neither key nor id survives the upgrade on its own: end-080 copies
    views, so an id of the new database can be one that never existed on the old, and the
    upgrade renames keys, so the key of a view that did survive can be another one. Verified
    on a real base: view 3785 went from ``website_sale.product_custom_text`` to
    ``website_sale.product_terms_and_conditions`` keeping its id.
    """
    cr.execute(SQL("SELECT id, key, website_id, active FROM %s", SQL.identifier(BACKUP_TABLE)))
    by_key, by_id = {}, {}
    for view_id, key, website_id, active in cr.fetchall():
        by_key[(key, website_id)] = active
        by_id[view_id] = active
    return by_key, by_id


def _taken_keys(cr):
    """The (key, website) pairs already in use, so no view is ever written onto another."""
    cr.execute("SELECT key, website_id FROM ir_ui_view WHERE website_id IS NOT NULL AND key IS NOT NULL")
    return set(cr.fetchall())


class _Discard(Exception):
    """Raised to roll back a savepoint whose work was never meant to be kept."""


def _forget(env):
    """Let the ORM and QWeb see what the SQL just changed.

    Both are needed: without the ormcache of templates QWeb renders the one it had compiled,
    and the page passes no matter what was written.
    """
    env.invalidate_all()
    env.transaction.invalidate_ormcache("templates")


def _renders(cr, env, site):
    """How the website renders, with whatever the render wrote thrown away.

    In a savepoint of its own, always rolled back: rendering a page can write (a cart, a
    visitor), and a render that fails on SQL would leave the cursor aborted for the rest of
    the ``-u``.
    """
    outcome = []
    try:
        with cr.savepoint():
            outcome.append(render_website(env, site))
            raise _Discard
    except _Discard:
        pass
    except Exception as e:
        outcome.append("%s: %s" % (type(e).__name__, str(e).splitlines()[0][:200] if str(e) else ""))
    _forget(env)
    return outcome[0]


def _restore_views(cr, by_key, by_id):
    env = util.env(cr)
    views = env["ir.ui.view"].with_context(active_test=False)
    candidates = views.search(
        [("key", "=like", "%" + SUFFIX), ("website_id", "!=", False), ("active", "=", False)]
    )
    taken = _taken_keys(cr)
    baselines = {}
    restored, archived, failed, unknown = [], [], [], 0
    for view in candidates:
        # The "_" of the suffix is a single-character wildcard for =like, so the pattern also
        # matches a key ending in anything + "depreciada": check the suffix for real.
        if not view.key.endswith(SUFFIX):
            continue
        site = view.website_id
        base_key = view.key[: -len(SUFFIX)]
        was_active = by_key.get((base_key, site.id))
        if was_active is None:
            # The key did not survive the upgrade: fall back to the id. A view born in the new
            # database carries an id from a sequence above every id of the old one, so it
            # matches nothing here.
            was_active = by_id.get(view.id)
        if was_active is None:
            # Not on the old database: a view the upgrade itself added, or a generic child
            # deprecated in cascade. Nothing to put back.
            unknown += 1
            continue
        label = "%s (website %s)" % (base_key, site.id)
        if (base_key, site.id) in taken:
            failed.append("%s (another view already holds that key)" % label)
            continue
        if was_active:
            # What the website looks like before touching it. If it is already broken, turning
            # a view back on proves nothing and the blame would land here.
            if site.id not in baselines:
                baselines[site.id] = _renders(cr, env, site)
                _logger.info("Website %s renders before the restore: %s", site.id, baselines[site.id])
            if baselines[site.id] != RENDER_OK:
                failed.append("%s (the website was already failing: %s)" % (label, baselines[site.id]))
                continue
        try:
            with cr.savepoint():
                cr.execute(
                    "UPDATE ir_ui_view SET key = %s, active = %s WHERE id = %s",
                    (base_key, was_active, view.id),
                )
                _forget(env)
                if was_active:
                    broken = _renders(cr, env, site)
                    if broken != RENDER_OK:
                        raise ValueError(broken)
        except Exception as e:
            _forget(env)
            failed.append("%s (%s)" % (label, str(e)[:300]))
            continue
        taken.add((base_key, site.id))
        (restored if was_active else archived).append(label)
    return restored, archived, failed, unknown


def _restore_wishlist(cr, by_key):
    """Take the wishlist off the shop cards of the websites that did not show it.

    In 20 the option no longer depends on a view: the addon that owned it is gone and only the
    classes decide. What a website showed on the old database is its own copy of the view if it
    had one, the generic view otherwise, and nothing at all when neither is in the backup: in 19
    website_sale_wishlist is auto_install on top of website_sale, so a base with no view of this
    key is one where the module was uninstalled by hand, and there the customer saw no wishlist
    even though the default of the field already carried the classes. Those three cases are the
    same decision, because only a view that was on means the customer saw it.

    The classes are only ever removed, never added.
    """
    if not util.module_installed(cr, "website_sale"):
        return []

    generic = by_key.get((WISHLIST_KEY, GENERIC_WEBSITE_ID))
    turned_off = []
    for site in util.env(cr)["website"].search([]):
        if by_key.get((WISHLIST_KEY, site.id), generic):
            continue
        classes = (site.shop_opt_products_design_classes or "").split()
        kept = [c for c in classes if c not in WISHLIST_CLASSES]
        if len(kept) == len(classes):
            continue
        site.write({"shop_opt_products_design_classes": " ".join(kept)})
        turned_off.append(site.id)
    return turned_off


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["website"], position="last"):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no website views to put back", BACKUP_TABLE)
        return

    by_key, by_id = _old_state(cr)
    restored, archived, failed, unknown = _restore_views(cr, by_key, by_id)
    turned_off = _restore_wishlist(cr, by_key)

    # Always, so an empty backup table does not read like a clean run.
    _logger.info(
        "Website views put back: %s on, %s archived with their key, %s failed, %s not on the "
        "old database; wishlist taken off %s websites (%s rows backed up)",
        len(restored), len(archived), len(failed), unknown, len(turned_off), len(by_key),
    )
    if restored:
        _logger.info("Back on, as before the upgrade: %s", ", ".join(restored))
    if archived:
        _logger.info("Off before the upgrade, archived with their key: %s", ", ".join(archived))
    if turned_off:
        _logger.info("Wishlist taken off the shop cards of the websites %s", turned_off)
    if failed:
        log_message(
            cr,
            "Website views that could not be put back as before the upgrade: %s" % "; ".join(failed),
            "warning",
            module="website",
        )
