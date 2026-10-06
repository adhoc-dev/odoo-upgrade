"""Unify the labels of the reconcile model lines with their base value, and fix the journal items.

The label is translatable and the journal item takes it in the language of whoever applies the
model. A model duplicated and relabeled in Spanish keeps the old label in en_US, which is what
the auto-reconcile cron (OdooBot, en_US) writes. The language is deduced per row: a key that
differs from en_US is the one that was edited. A row with two such keys is reported and left
as is, with its journal items.

Journal items are fixed only for models with a single line: the item stores the model, not the
line. Items in hashed moves are fixed too, by product decision, and counted apart because
their hash no longer matches. Idempotent: a second run finds nothing to change.

Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import re

from odoo import release
from odoo.upgrade import util
from oba import log_message, request_context

# Upgrades to 19 still run the upgrade line 2498.
FIRST_TARGET_VERSION = 20

# Journal items whose label differs from the current label of a line edited in a customer
# language, out of the ambiguous lines. Completed with the condition on the number of lines.
STALE_ITEMS = """
      FROM account_move_line aml
      JOIN account_reconcile_model_line l ON l.model_id = aml.reconcile_model_id
      {join}
     WHERE aml.name IS DISTINCT FROM l.label ->> 'en_US'
       AND COALESCE(l.label ->> 'en_US', '') != ''
       AND EXISTS (SELECT 1 FROM jsonb_each_text(l.label) x WHERE x.key != 'en_US' AND COALESCE(x.value, '') != '')
       AND l.id != ALL(%s)
       AND (SELECT COUNT(*) FROM account_reconcile_model_line l2 WHERE l2.model_id = aml.reconcile_model_id) {lines}
"""


def migrate(cr, version):
    # Only on a major upgrade.
    match = re.search(r"\d+", version or "")
    if not match or int(match.group()) >= release.version_info[0]:
        return

    if release.version_info[0] < FIRST_TARGET_VERSION:
        return

    if not util.module_installed(cr, "account_accountant"):
        return

    if not request_context(cr).get("is_last_in_series", True):
        return

    cr.execute("SELECT 1 FROM account_reconcile_model_line LIMIT 1")
    if not cr.rowcount:
        return

    cr.execute(
        """
        SELECT l.id,
               array_agg(k.key ORDER BY k.key),
               array_agg(k.value ORDER BY k.key),
               min(COALESCE(m.name ->> k.key, m.name ->> 'en_US')),
               min(l.label ->> 'en_US')
          FROM account_reconcile_model_line l
          JOIN account_reconcile_model m ON m.id = l.model_id
         CROSS JOIN LATERAL jsonb_each_text(l.label) k
         WHERE k.key != 'en_US'
           AND COALESCE(k.value, '') != ''
           AND k.value IS DISTINCT FROM l.label ->> 'en_US'
         GROUP BY l.id
         ORDER BY 4
        """
    )
    candidates = cr.fetchall()
    to_unify = [row for row in candidates if len(row[1]) == 1]
    ambiguous = [row for row in candidates if len(row[1]) > 1]
    if to_unify:
        lines_by_lang = {}
        for row in to_unify:
            lines_by_lang.setdefault(row[1][0], []).append(row[0])
        for lang_code, line_ids in lines_by_lang.items():
            cr.execute(
                """
                UPDATE account_reconcile_model_line
                   SET label = jsonb_set(label, '{en_US}', label -> %s)
                 WHERE id = ANY(%s)
                """,
                (lang_code, line_ids),
            )
        detail = " | ".join('%s: "%s" -> "%s" (%s)' % (row[3], row[4], row[2][0], row[1][0]) for row in to_unify)
        log_message(cr, "Reconcile model labels unified (%s lines): %s" % (len(to_unify), detail), "info")
    if ambiguous:
        detail = " | ".join(
            "%s (line %s): %s"
            % (row[3], row[0], ", ".join('%s="%s"' % (lang, label) for lang, label in zip(row[1], row[2])))
            for row in ambiguous
        )
        log_message(
            cr,
            "Reconcile model labels edited in more than one language, left as they are because the right"
            " one cannot be told (%s lines): %s" % (len(ambiguous), detail),
            "warning",
        )

    # Runs after unifying, so the right label of each line is already the en_US one.
    # 0 is not an id: avoids an empty untyped array.
    ambiguous_ids = [row[0] for row in ambiguous] or [0]
    cr.execute(
        """
        SELECT COALESCE((SELECT x.value FROM jsonb_each_text(m.name) x WHERE x.key != 'en_US' LIMIT 1),
                        m.name ->> 'en_US'),
               aml.name, l.label ->> 'en_US', COUNT(*)
        """
        + STALE_ITEMS.format(join="JOIN account_reconcile_model m ON m.id = l.model_id", lines="= 1")
        + " GROUP BY 1, 2, 3 ORDER BY 4 DESC",
        (ambiguous_ids,),
    )
    items = cr.fetchall()
    cr.execute(
        "SELECT COUNT(*)"
        + STALE_ITEMS.format(join="JOIN account_move mv ON mv.id = aml.move_id", lines="= 1")
        + " AND mv.inalterable_hash IS NOT NULL",
        (ambiguous_ids,),
    )
    hashed = cr.fetchone()[0]
    cr.execute("SELECT COUNT(DISTINCT aml.id)" + STALE_ITEMS.format(join="", lines="> 1"), (ambiguous_ids,))
    skipped = cr.fetchone()[0]
    if items:
        cr.execute(
            "UPDATE account_move_line item SET name = stale.label FROM (SELECT aml.id, l.label ->> 'en_US' AS label"
            + STALE_ITEMS.format(join="", lines="= 1")
            + ") stale WHERE item.id = stale.id",
            (ambiguous_ids,),
        )
        detail = " | ".join('%s: %s items "%s" -> "%s"' % (row[0], row[3], row[1], row[2]) for row in items)
        log_message(
            cr,
            "Journal items of reconcile models fixed (%s items): %s" % (sum(row[3] for row in items), detail),
            "info",
        )
    if hashed:
        log_message(
            cr,
            "%s of the fixed journal items belong to moves with an inalterability hash. The label is part of"
            " the hash, so the inalterability report will show those moves as altered." % hashed,
            "warning",
        )
    if skipped:
        log_message(
            cr,
            "%s journal items keep a label different from their model and are not fixed: the model has more"
            " than one line and the item stores the model, not the line." % skipped,
            "info",
        )
