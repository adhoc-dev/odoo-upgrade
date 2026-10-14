"""Move the journal book groups of ``account_journal_book_report`` to ledgers.

The module is retired in 20: the Argentinean daily book of ``l10n_ar_reports`` summarizes by
month the journals that have a ledger (``account.journal.journal_group_id``), where the module
used ``account.journal.book_group_id``. One ledger per book group name, set on the journals
that had that group.

The module tables are ours, so the pass to Odoo leaves them as they were: read here, before
``end-900`` removes the module with them.

A journal has only one ledger, and having one takes it out of the Local GAAP reports:
- a journal that already has a ledger keeps it, so a parallel accounting (IFRS, tax) is not
  broken; it loses its monthly summary in the daily book;
- ledger names are unique in 20: a book group named like an existing ledger gets a new ledger
  with a suffix, so its journals do not join the parallel accounting of the other one.
Both cases go to the request as a warning.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

# The module is retired in 20.
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20
MODULE = "account_journal_book_report"
NAME_SUFFIX = " (Libro diario)"


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=[MODULE]):
        return
    if not util.table_exists(cr, "account_journal_book_group") or not util.column_exists(
        cr, "account_journal", "book_group_id"
    ):
        # Nobody looked: do not report a clean move.
        log_message(cr, "%s: no book groups found to move to ledgers" % MODULE, "warning")
        return

    cr.execute(
        SQL(
            """
            SELECT g.name, array_agg(j.id ORDER BY j.id)
              FROM account_journal j
              JOIN account_journal_book_group g ON g.id = j.book_group_id
             GROUP BY g.name
             ORDER BY g.name
            """
        )
    )
    groups = cr.fetchall()
    if not groups:
        _logger.info("No journal has a book group")
        return

    env = util.env(cr)
    Ledger = env["account.journal.group"].with_context(lang="en_US", active_test=False)
    Journal = env["account.journal"].with_context(active_test=False)
    with_ledger, renamed = [], []
    for name, journal_ids in groups:
        journals = Journal.browse(journal_ids)
        with_ledger += journals.filtered("journal_group_id").ids
        journals = journals.filtered(lambda j: not j.journal_group_id)
        if not journals:
            continue
        ledger_name = name
        if Ledger.search_count([("name", "=", name)]):
            ledger_name = name + NAME_SUFFIX
            renamed.append(name)
        ledger = Ledger.create({"name": ledger_name})
        journals.write({"journal_group_id": ledger.id})
        _logger.info("Ledger %r set on journals %s", ledger_name, journals.ids)

    if with_ledger:
        log_message(
            cr,
            "%s: these journals already had a ledger and kept it, without their book group: %s"
            % (MODULE, with_ledger),
            "warning",
        )
    if renamed:
        log_message(
            cr,
            "%s: these book groups took a name already used by a ledger, created with %r: %s"
            % (MODULE, NAME_SUFFIX, renamed),
            "warning",
        )
