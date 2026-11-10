import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message

_logger = logging.getLogger(__name__)

# The 19 withholding lines of l10n_ar_tax. Odoo drops the table when it cleans up the removed model,
# after the post-migrations, so it is still there when this runs.
OLD_TABLE = "l10n_ar_payment_withholding"
NEW_TABLE = "account_payment_withholding_line"
# Old line -> new line, kept for the modules that added columns to the old lines
# (l10n_ar_arba_ws, l10n_ar_tax_backward_compatibility).
MAP_TABLE = "l10n_ar_payment_withholding_map_bu"


def migrate(cr, version):
    """Move the 19 withholding lines to account.payment.withholding.line and make the payments gross.

    In 19 the lines of l10n_ar_tax are in company currency (ARS) and the payment amount is the net one.
    In 20 the lines are Odoo's, in the payment currency valued at the payment rate (`accounting_rate`,
    payment currency per company currency), and the payment amount is the gross one: Odoo computes the
    net as amount minus withholdings. l10n_ar_tax also stores the ARS of each line
    (`l10n_ar_base_amount`, `l10n_ar_amount`), the ones the entry and the certificate use: they are the
    19 amounts, as they are.

    The lines are inserted with SQL: `base_amount`, `amount` and `account_id` are stored computes, and the
    ORM would recompute them with today's rates, registers and accumulations. The posted entries are not
    touched.

    It also leaves the AR taxes valid for the 20 rules that our 19 data can break.
    """
    _logger.info("Running post-migration for l10n_ar_tax version %s", version)

    _clean_withholding_type_of_other_taxes(cr)
    _warn_earnings_without_code(cr)

    if not util.table_exists(cr, OLD_TABLE):
        _logger.info("No %s table: nothing to migrate", OLD_TABLE)
        return

    cr.execute(
        SQL(
            """
            CREATE TABLE IF NOT EXISTS %s (
                old_id integer PRIMARY KEY,
                new_id integer NOT NULL,
                payment_id integer NOT NULL,
                gross_done boolean NOT NULL DEFAULT FALSE
            )
            """,
            SQL.identifier(MAP_TABLE),
        )
    )

    _warn_missing_rate(cr)
    _warn_missing_account(cr)
    _insert_lines(cr)
    _make_payments_gross(cr)


def _ar_taxes(where):
    return SQL(
        """
        SELECT t.id
          FROM account_tax t
          JOIN res_country co ON co.id = t.country_id
         WHERE co.code = 'AR'
           AND %s
        """,
        where,
    )


def _has_withholding_columns(cr):
    return all(
        util.column_exists(cr, "account_tax", column)
        for column in ("is_withholding_tax", "l10n_ar_withholding_tax_type", "country_id")
    )


def _clean_withholding_type_of_other_taxes(cr):
    """In 20 only a withholding tax can have a withholding type; in 19 our perceptions had one.

    The perceptions of 20 do not read it, and while it is set the tax cannot be saved. Nothing to do when
    the upgrade already cleaned it.
    """
    if not _has_withholding_columns(cr):
        return
    cr.execute(
        SQL(
            """
            UPDATE account_tax
               SET l10n_ar_withholding_tax_type = NULL
             WHERE id IN (%s)
            RETURNING id
            """,
            _ar_taxes(
                SQL("NOT COALESCE(t.is_withholding_tax, FALSE) AND t.l10n_ar_withholding_tax_type IS NOT NULL")
            ),
        )
    )
    tax_ids = sorted(tax_id for (tax_id,) in cr.fetchall())
    if tax_ids:
        log_message(
            cr,
            "%s AR taxes that are not withholdings lost their withholding type (account.tax ids %s)"
            % (len(tax_ids), tax_ids),
            module="l10n_ar_tax",
        )


def _warn_earnings_without_code(cr):
    """In 20 a purchase earnings withholding needs its ARCA code to be saved. The code is not guessed."""
    if not (_has_withholding_columns(cr) and util.column_exists(cr, "account_tax", "l10n_ar_code")):
        return
    cr.execute(
        SQL(
            "SELECT array_agg(id ORDER BY id) FROM (%s) s",
            _ar_taxes(
                SQL(
                    """
                    t.is_withholding_tax
                    AND t.type_tax_use = 'purchase'
                    AND t.l10n_ar_withholding_tax_type IN ('earnings', 'earnings_scale')
                    AND COALESCE(t.l10n_ar_code, '') = ''
                    """
                )
            ),
        )
    )
    tax_ids = cr.fetchone()[0]
    if tax_ids:
        log_message(
            cr,
            "%s earnings withholding taxes have no ARCA code, and they cannot be edited until somebody sets it "
            "(account.tax ids %s)" % (len(tax_ids), tax_ids),
            "warning",
            module="l10n_ar_tax",
        )


def _pending_lines():
    """Old lines still to migrate, with what the new line needs.

    A payment in a foreign currency without `accounting_rate` cannot be valued, and a line without an
    account cannot be inserted. Either one leaves the whole payment out, lines and gross amount, so
    that it does not end up with part of its withholdings; the warnings tell which.
    """
    return SQL(
        """
        SELECT w.id AS old_id,
               w.payment_id,
               w.tax_id,
               p.company_id,
               NULLIF(w.name, '') AS name,
               w.ref,
               w.create_uid,
               w.create_date,
               w.write_uid,
               w.write_date,
               CASE WHEN p.currency_id = c.currency_id THEN w.base_amount
                    ELSE ROUND(w.base_amount * p.accounting_rate::numeric, cur.decimal_places)
               END AS base_amount,
               CASE WHEN p.currency_id = c.currency_id THEN w.amount
                    ELSE ROUND(w.amount * p.accounting_rate::numeric, cur.decimal_places)
               END AS amount,
               w.base_amount AS l10n_ar_base_amount,
               w.amount AS l10n_ar_amount,
               COALESCE(
                   (SELECT aml.account_id
                      FROM account_move_line aml
                     WHERE aml.move_id = p.move_id
                       AND aml.tax_line_id = w.tax_id
                     ORDER BY aml.id
                     LIMIT 1),
                   (SELECT rl.account_id
                      FROM account_tax_repartition_line rl
                     WHERE rl.tax_id = w.tax_id
                       AND rl.repartition_type = 'tax'
                       AND rl.document_type = 'invoice'
                       AND rl.account_id IS NOT NULL
                     ORDER BY rl.sequence, rl.id
                     LIMIT 1)
               ) AS account_id,
               (p.currency_id <> c.currency_id AND COALESCE(p.accounting_rate, 0) = 0) AS missing_rate
          FROM %(old)s w
          JOIN account_payment p ON p.id = w.payment_id
          JOIN res_company c ON c.id = p.company_id
          JOIN res_currency cur ON cur.id = p.currency_id
         WHERE NOT EXISTS (SELECT 1 FROM %(map)s m WHERE m.old_id = w.id)
        """,
        old=SQL.identifier(OLD_TABLE),
        map=SQL.identifier(MAP_TABLE),
    )


def _warn_missing_rate(cr):
    cr.execute(
        SQL(
            "SELECT array_agg(DISTINCT payment_id ORDER BY payment_id) FROM (%s) s WHERE missing_rate",
            _pending_lines(),
        )
    )
    payment_ids = cr.fetchone()[0]
    if payment_ids:
        log_message(
            cr,
            "%s payments in a foreign currency have no accounting rate: their withholdings were not migrated "
            "and their amount stays net (account.payment ids %s)" % (len(payment_ids), payment_ids),
            "warning",
            module="l10n_ar_tax",
        )


def _warn_missing_account(cr):
    cr.execute(
        SQL(
            "SELECT array_agg(old_id ORDER BY old_id) FROM (%s) s WHERE account_id IS NULL AND NOT missing_rate",
            _pending_lines(),
        )
    )
    old_ids = cr.fetchone()[0]
    if old_ids:
        log_message(
            cr,
            "%s withholding lines have no account in the payment entry nor in their tax: their payments "
            "were not migrated and keep the net amount (%s ids %s)" % (len(old_ids), OLD_TABLE, old_ids),
            "warning",
            module="l10n_ar_tax",
        )


def _insert_lines(cr):
    # The new ids are taken in the CTE, so the same statement inserts the line and its map row.
    cr.execute(
        SQL(
            """
            WITH src AS MATERIALIZED (
                SELECT s.*, nextval(pg_get_serial_sequence(%(new_name)s, 'id')) AS new_id
                  FROM (%(pending)s) s
                 WHERE s.payment_id NOT IN (
                       SELECT b.payment_id FROM (%(pending)s) b WHERE b.account_id IS NULL OR b.missing_rate
                   )
            ),
            ins AS (
                INSERT INTO %(new)s (
                    id, payment_id, tax_id, company_id, account_id, name, ref,
                    placeholder_type, previous_placeholder_type, base_amount, amount,
                    l10n_ar_base_amount, l10n_ar_amount,
                    create_uid, create_date, write_uid, write_date
                )
                SELECT new_id, payment_id, tax_id, company_id, account_id, name, ref,
                       CASE WHEN name IS NULL THEN 'not_defined' ELSE 'given_by_name' END,
                       CASE WHEN name IS NULL THEN 'not_defined' ELSE 'given_by_name' END,
                       base_amount, amount,
                       l10n_ar_base_amount, l10n_ar_amount,
                       create_uid, create_date, write_uid, write_date
                  FROM src
            )
            INSERT INTO %(map)s (old_id, new_id, payment_id)
            SELECT old_id, new_id, payment_id FROM src
            """,
            new_name=NEW_TABLE,
            pending=_pending_lines(),
            new=SQL.identifier(NEW_TABLE),
            map=SQL.identifier(MAP_TABLE),
        )
    )
    _logger.info("%s withholding lines moved to %s", cr.rowcount, NEW_TABLE)


def _make_payments_gross(cr):
    """In 19 the payment amount is the net one; in 20 it is the net plus the withholdings.

    Only the payments whose lines were all migrated, and once: `gross_done` marks them. With
    account_payment_pro, `amount_exact` (when set) and `counterpart_currency_amount` follow `amount`.
    """
    cr.execute("DROP TABLE IF EXISTS l10n_ar_tax_gross")
    cr.execute(
        SQL(
            """
            CREATE TEMP TABLE l10n_ar_tax_gross AS
            SELECT m.payment_id, SUM(n.amount) AS withholding
              FROM %(map)s m
              JOIN %(new)s n ON n.id = m.new_id
             WHERE NOT m.gross_done
               AND NOT EXISTS (
                   SELECT 1
                     FROM %(old)s w
                    WHERE w.payment_id = m.payment_id
                      AND NOT EXISTS (SELECT 1 FROM %(map)s m2 WHERE m2.old_id = w.id)
               )
             GROUP BY m.payment_id
            """,
            map=SQL.identifier(MAP_TABLE),
            new=SQL.identifier(NEW_TABLE),
            old=SQL.identifier(OLD_TABLE),
        )
    )
    cr.execute("UPDATE account_payment p SET amount = p.amount + g.withholding FROM l10n_ar_tax_gross g WHERE p.id = g.payment_id")
    _logger.info("%s payments moved to the gross amount", cr.rowcount)

    if util.column_exists(cr, "account_payment", "amount_exact"):
        cr.execute(
            """
            UPDATE account_payment p
               SET amount_exact = p.amount_exact + g.withholding
              FROM l10n_ar_tax_gross g
             WHERE p.id = g.payment_id
               AND COALESCE(p.amount_exact, 0) <> 0
            """
        )
    if util.column_exists(cr, "account_payment", "counterpart_currency_amount"):
        cr.execute(
            """
            UPDATE account_payment p
               SET counterpart_currency_amount = p.counterpart_currency_amount + CASE
                       WHEN p.counterpart_currency_id IS NOT NULL AND p.counterpart_currency_id <> p.currency_id
                       THEN ROUND(g.withholding * COALESCE(p.counterpart_rate, 0)::numeric, cur.decimal_places)
                       ELSE g.withholding
                   END
              FROM l10n_ar_tax_gross g, res_currency cur
             WHERE p.id = g.payment_id
               AND cur.id = COALESCE(p.counterpart_currency_id, p.currency_id)
            """
        )

    cr.execute(
        SQL(
            "UPDATE %s m SET gross_done = TRUE FROM l10n_ar_tax_gross g WHERE m.payment_id = g.payment_id",
            SQL.identifier(MAP_TABLE),
        )
    )
    cr.execute("DROP TABLE l10n_ar_tax_gross")
