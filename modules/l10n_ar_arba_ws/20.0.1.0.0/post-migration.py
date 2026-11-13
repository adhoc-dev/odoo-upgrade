import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)

# The 19 withholding lines of l10n_ar_tax, still there until the old model is removed after the post-migrations.
OLD_TABLE = "l10n_ar_payment_withholding"
NEW_TABLE = "account_payment_withholding_line"
# Old line -> new line, left by the post-migration of l10n_ar_tax 20.0.1.0.0, which runs before this one
# because l10n_ar_arba_ws depends on l10n_ar_tax.
MAP_TABLE = "l10n_ar_payment_withholding_map_bu"
COLUMNS = ("l10n_ar_cert_number", "l10n_ar_dj_arba_id")


def migrate(cr, version):
    """Keep the ARBA certificate and DDJJ of the withholdings already informed.

    In 20 the withholding lines are account.payment.withholding.line, and l10n_ar_tax moves its own columns
    (name and ref among them). The two columns this module added to the 19 lines do not travel with them:
    without them an informed withholding shows the ARBA button again, can be informed twice, goes back to the
    batch TXT of the PBA report and the draft warning of the payment does not show up.
    """
    _logger.info("Running post-migration for l10n_ar_arba_ws version %s", version)

    if not util.table_exists(cr, OLD_TABLE):
        _logger.info("No %s table: nothing to migrate", OLD_TABLE)
        return
    if not all(util.column_exists(cr, OLD_TABLE, column) for column in COLUMNS):
        _logger.info("%s has no ARBA columns: nothing to migrate", OLD_TABLE)
        return
    if not util.table_exists(cr, MAP_TABLE):
        log_message(
            cr,
            "%s is missing, so the ARBA certificates and DDJJ of the withholdings were not migrated: "
            "did the post-migration of l10n_ar_tax 20.0.1.0.0 run?" % MAP_TABLE,
            "error",
            module="l10n_ar_arba_ws",
        )
        return

    cr.execute(
        SQL(
            """
            UPDATE %(new)s AS new
               SET l10n_ar_cert_number = old.l10n_ar_cert_number,
                   l10n_ar_dj_arba_id = old.l10n_ar_dj_arba_id
              FROM %(map)s AS map
              JOIN %(old)s AS old ON old.id = map.old_id
             WHERE new.id = map.new_id
               AND (old.l10n_ar_cert_number IS NOT NULL OR old.l10n_ar_dj_arba_id IS NOT NULL)
               AND new.l10n_ar_cert_number IS NULL
               AND new.l10n_ar_dj_arba_id IS NULL
            """,
            new=SQL.identifier(NEW_TABLE),
            map=SQL.identifier(MAP_TABLE),
            old=SQL.identifier(OLD_TABLE),
        )
    )
    _logger.info("%s withholding lines got their ARBA certificate or DDJJ", cr.rowcount)

    _warn_unmapped(cr)


def _warn_unmapped(cr):
    """An informed 19 line that l10n_ar_tax did not move keeps its certificate only in the old table."""
    cr.execute(
        SQL(
            """
            SELECT array_agg(old.id ORDER BY old.id)
              FROM %(old)s AS old
         LEFT JOIN %(map)s AS map ON map.old_id = old.id
             WHERE map.old_id IS NULL
               AND (old.l10n_ar_cert_number IS NOT NULL OR old.l10n_ar_dj_arba_id IS NOT NULL)
            """,
            old=SQL.identifier(OLD_TABLE),
            map=SQL.identifier(MAP_TABLE),
        )
    )
    old_ids = cr.fetchone()[0]
    if old_ids:
        log_message(
            cr,
            "%s withholdings informed to ARBA were not moved to 20 by l10n_ar_tax, so they lost their certificate "
            "and DDJJ (l10n_ar.payment.withholding ids %s)" % (len(old_ids), old_ids),
            "warning",
            module="l10n_ar_arba_ws",
        )
