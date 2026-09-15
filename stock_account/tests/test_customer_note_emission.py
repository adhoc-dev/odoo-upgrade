"""The customer note channel, end to end, on a real upgrade.

What this proves is the claim the channel makes: a migration script emits while the upgrade
runs, and what it emitted is still there once the upgrade is over, on the new database, for
the provider to read. Until now the detection lived in a text field of another database and
could not be tested at any level.

It needs no seeding because ``stock_account/19.0.0.0/end-migration.py`` emits on every
upgrade, empty lists included -- that is deliberate, so a run that no longer finds anything
overwrites the previous run's values instead of leaving them standing.

What it does NOT prove is that the rows are the *right* ones. That needs orders seeded in 18
that land in scenarios B and D once migrated, which is business data this test has no way to
build blind; it belongs in a second case, with a run behind it.
"""

from odoo.upgrade.testing import UpgradeCase

TABLE = "oba_upgrade_customer_note"
SLUG = "valoracion-stock-accionables"
EXPECTED_KEYS = {"escenario_b_rows", "escenario_d_rows"}


class StockValuationCustomerNoteEmitted(UpgradeCase):
    def prepare(self):
        # Nothing to seed: the emitter runs on every upgrade of stock_account.
        return True

    def check(self, value):
        cr = self.env.cr

        cr.execute("SELECT to_regclass(%s)", [TABLE])
        self.assertTrue(
            cr.fetchone()[0],
            "%s does not exist: no upgrade script called add_customer_note. The helper "
            "creates the table itself, so this means the emitter never ran." % TABLE,
        )

        cr.execute("SELECT module, vals, created_at FROM %s WHERE slug = %%s" % TABLE, [SLUG])
        rows = cr.fetchall()
        self.assertEqual(
            len(rows),
            1,
            "expected exactly one row for %r, got %s. More than one means the upsert by slug "
            "is not holding; none means the emitter did not run." % (SLUG, len(rows)),
        )

        module, vals, created_at = rows[0]
        self.assertEqual(module, "stock_account", "the module is taken from the emitter's path")
        self.assertIsNotNone(created_at, "created_at is what says which run wrote the values")
        self.assertEqual(
            set(vals),
            EXPECTED_KEYS,
            "the note's message renders these names, so the emitter must keep sending exactly them",
        )
        for key in EXPECTED_KEYS:
            self.assertIsInstance(vals[key], list, "%s must survive jsonb as a list" % key)
