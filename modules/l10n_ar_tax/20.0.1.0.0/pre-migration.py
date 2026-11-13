import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Copy the jurisdiction and the withholding sequence of the AR taxes to their tax group.

    In 20 l10n_ar_tax keeps both in account.tax.group, and the tax reads them from there: the jurisdiction
    for every AR tax, the sequence only for the supplier withholdings (a customer withholding carries the
    number of the customer's certificate). This runs before the module is loaded, so the groups already
    have the values when the tax fields become computed from them.

    A group takes a value when all its AR taxes that have one agree; the sequence is compared among its
    supplier withholdings only. A tax without value takes the one of its group, and the log lists it. When
    two taxes have different values the script does not choose: the group stays empty and a warning lists
    it, because it is a configuration error.
    """
    _logger.info("Running pre-migration for l10n_ar_tax version %s", version)
    if not util.table_exists(cr, "account_tax_group"):
        return
    util.create_column(cr, "account_tax_group", "l10n_ar_state_id", "int4")
    util.create_column(cr, "account_tax_group", "withholding_sequence_id", "int4")

    _copy_to_group(cr, "l10n_ar_state_id", SQL("TRUE"), "jurisdiction")
    _copy_to_group(
        cr,
        "withholding_sequence_id",
        SQL("t.type_tax_use = 'purchase' AND COALESCE(t.is_withholding_tax, FALSE)"),
        "withholding sequence",
    )
    _warn_lost_sequences(cr)


def _copy_to_group(cr, column, taxes_filter, label):
    # Groups whose AR taxes (of the filter) have some value: the ones with a single value take it, and
    # their taxes without value get it too; the rest are warned.
    query = SQL(
        """
        WITH groups AS (
            SELECT t.tax_group_id AS group_id,
                   count(DISTINCT t.%(column)s) AS n_values,
                   max(t.%(column)s) AS value,
                   array_agg(t.id) FILTER (WHERE t.%(column)s IS NULL) AS taxes_without_value,
                   string_agg(t.id || ':' || COALESCE(t.%(column)s::text, '-'), ', ' ORDER BY t.id) AS detail
              FROM account_tax t
              JOIN res_country co ON co.id = t.country_id
             WHERE co.code = 'AR'
               AND t.tax_group_id IS NOT NULL
               AND %(taxes_filter)s
             GROUP BY t.tax_group_id
            HAVING count(t.%(column)s) > 0
        ), updated AS (
            UPDATE account_tax_group g
               SET %(column)s = groups.value
              FROM groups
             WHERE g.id = groups.group_id
               AND groups.n_values = 1
               AND g.%(column)s IS NULL
            RETURNING g.id
        )
        SELECT (SELECT count(*) FROM updated),
               (SELECT array_agg(groups.group_id || ' (' || groups.detail || ')' ORDER BY groups.group_id)
                  FROM groups
                 WHERE groups.n_values > 1),
               (SELECT array_agg(tax_id ORDER BY tax_id)
                  FROM groups, unnest(groups.taxes_without_value) AS tax_id
                 WHERE groups.n_values = 1)
        """,
        column=SQL.identifier(column),
        taxes_filter=taxes_filter,
    )
    cr.execute(query)
    n_updated, conflicts, filled_tax_ids = cr.fetchone()
    _logger.info("%s AR tax groups took the %s of their taxes", n_updated, label)
    if filled_tax_ids:
        # The update does not recompute the taxes from their group, so they get the value here.
        cr.execute(
            SQL(
                """
                UPDATE account_tax t
                   SET %(column)s = g.%(column)s
                  FROM account_tax_group g
                 WHERE g.id = t.tax_group_id
                   AND t.id = ANY(%(tax_ids)s)
                """,
                column=SQL.identifier(column),
                tax_ids=filled_tax_ids,
            )
        )
        log_message(
            cr,
            "%s AR taxes without %s take the one of their tax group (account.tax ids %s)"
            % (len(filled_tax_ids), label, filled_tax_ids),
            module="l10n_ar_tax",
        )
    if conflicts:
        log_message(
            cr,
            "%s AR tax groups have taxes with a different %s and were left without one: set it on the group "
            "(account.tax.group id (account.tax id:value, ...)): %s" % (len(conflicts), label, "; ".join(conflicts)),
            "warning",
            module="l10n_ar_tax",
        )


def _warn_lost_sequences(cr):
    """Only supplier withholdings take the sequence of their group: any other AR tax loses the one it had.

    The update does not recompute the taxes, so the sequence is removed here.
    """
    cr.execute(
        SQL(
            """
            WITH lost AS (
                UPDATE account_tax t
                   SET withholding_sequence_id = NULL
                  FROM res_country co
                 WHERE co.id = t.country_id
                   AND co.code = 'AR'
                   AND t.withholding_sequence_id IS NOT NULL
                   AND NOT (t.type_tax_use = 'purchase' AND COALESCE(t.is_withholding_tax, FALSE))
                RETURNING t.id
            )
            SELECT array_agg(id ORDER BY id) FROM lost
            """
        )
    )
    tax_ids = cr.fetchone()[0]
    if tax_ids:
        log_message(
            cr,
            "%s AR taxes that are not supplier withholdings lose their withholding sequence: their number is "
            "entered on each payment (account.tax ids %s)" % (len(tax_ids), tax_ids),
            module="l10n_ar_tax",
        )
