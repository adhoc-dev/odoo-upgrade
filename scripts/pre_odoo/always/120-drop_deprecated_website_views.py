import logging

from oba import should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 2004.
FIRST_TARGET_VERSION = 20
# Left by modules/base/0.0.0/end-180-deprecate_website_custom_views.py (upgrade line 664)
# on the previous upgrade. Same pattern as the upgrade line: "_" matches any character.
DEPRECATED_KEY = "%_depreciada%"


def migrate(cr, version):
    """Drop the website views deprecated on the previous upgrade, before the database is sent to Odoo.

    Leaves first: a view with children cannot be deleted (inherit_id is ondelete restrict),
    so each round drops the views no other view inherits from, until none is left. A view
    that another record still points to with a restrict foreign key is archived instead, as
    the upgrade line did when the unlink failed.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    The xmlids of a dropped view go with it, as the ORM unlink did.
    """
    if not should_run_pre_odoo(cr, FIRST_TARGET_VERSION, modules=["website"]):
        return

    cr.execute("SELECT id FROM ir_ui_view WHERE key ILIKE %s", (DEPRECATED_KEY,))
    remaining = {row[0] for row in cr.fetchall()}
    if not remaining:
        return
    blockers = _restrict_references(cr)

    dropped, archived, failed = [], [], []
    while remaining:
        cr.execute(
            """
            SELECT v.id
              FROM ir_ui_view v
             WHERE v.id = ANY(%s)
               AND NOT EXISTS (SELECT 1 FROM ir_ui_view c WHERE c.inherit_id = v.id)
             ORDER BY v.id
            """,
            (sorted(remaining),),
        )
        leaves = [row[0] for row in cr.fetchall()]
        if not leaves:
            break
        remaining.difference_update(leaves)
        for view_id in leaves:
            if _is_referenced(cr, blockers, view_id):
                cr.execute("UPDATE ir_ui_view SET active = false WHERE id = %s", (view_id,))
                archived.append(view_id)
                continue
            # A cascade can still hit a restrict further down: that view stays, the rest goes on.
            cr.execute("SAVEPOINT drop_deprecated_view")
            try:
                cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = %s", (view_id,))
                cr.execute("DELETE FROM ir_ui_view WHERE id = %s", (view_id,))
            except Exception as e:
                cr.execute("ROLLBACK TO SAVEPOINT drop_deprecated_view")
                failed.append("%s (%s)" % (view_id, str(e).splitlines()[0][:200]))
            else:
                cr.execute("RELEASE SAVEPOINT drop_deprecated_view")
                dropped.append(view_id)

    _logger.info("Deprecated website views dropped: %s; archived: %s", dropped, archived)
    if remaining:
        _logger.info("Deprecated website views left, with children that stay: %s", sorted(remaining))
    if failed:
        _logger.warning("Deprecated website views that could not be dropped: %s", "; ".join(failed))


def _restrict_references(cr):
    """The (table, column) pairs that point to ir_ui_view and block a delete."""
    cr.execute(
        """
        SELECT c.conrelid::regclass::text, a.attname
          FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
         WHERE c.contype = 'f'
           AND c.confrelid = 'ir_ui_view'::regclass
           AND c.confdeltype IN ('a', 'r')
        """
    )
    return cr.fetchall()


def _is_referenced(cr, blockers, view_id):
    for table, column in blockers:
        # Names from pg_catalog, not from data.
        cr.execute('SELECT 1 FROM %s WHERE "%s" = %%s LIMIT 1' % (table, column), (view_id,))
        if cr.fetchone():
            return True
    return False
