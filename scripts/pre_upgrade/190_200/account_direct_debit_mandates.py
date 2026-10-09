import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# The other half: scripts/pre_odoo/190_200/010-module_renames.py renames account_direct_debit
# to account_direct_debit_ux before the dump. Here our mandates become Odoo's.
TABLE = "account_direct_debit_mandate"


def migrate(cr, version):
    if not util.module_installed(cr, "account_direct_debit_ux"):
        return

    _logger.info("Moving direct debit mandates to Odoo's account.direct.debit.mandate")
    # Same table name for both models, so only the references change
    util.rename_model(cr, "account.direct_debit.mandate", "account.direct.debit.mandate")
    util.rename_field(cr, "account.payment", "direct_debit_mandate_id", "mandate_id")
    # Each format becomes the mandate type with the same key: the journal keeps its value
    util.rename_field(cr, "account.journal", "direct_debit_format", "direct_debit_mandate_type")

    # Odoo's mandate requires these. Filled before its install, or every mandate would get
    # the same default identifier and break its unique constraint.
    util.create_column(cr, TABLE, "name", "varchar")
    util.create_column(cr, TABLE, "start_date", "date")
    util.create_column(cr, TABLE, "mandate_type", "varchar")
    cr.execute(
        SQL(
            """
            UPDATE %(table)s
               SET name = COALESCE(name, 'DD-' || id),
                   start_date = COALESCE(start_date, create_date::date)
            """,
            table=SQL.identifier(TABLE),
        )
    )
    _fill_mandate_type(cr)
    _fill_company(cr)

    util.force_install_module(cr, "account_direct_debit")


def _fill_mandate_type(cr):
    cr.execute(
        SQL(
            """
            UPDATE %(table)s m
               SET mandate_type = j.direct_debit_mandate_type
              FROM account_journal j
             WHERE j.id = m.journal_id
               AND m.mandate_type IS NULL
            """,
            table=SQL.identifier(TABLE),
        )
    )
    cr.execute(SQL("SELECT array_agg(id) FROM %(table)s WHERE mandate_type IS NULL", table=SQL.identifier(TABLE)))
    if missing := cr.fetchone()[0]:
        # E.g. a mandate without journal, or on a journal without format
        _logger.warning("Direct debit mandates without mandate type, Odoo requires one: %s", missing)


def _fill_company(cr):
    cr.execute(
        SQL(
            """
            UPDATE %(table)s m
               SET company_id = j.company_id
              FROM account_journal j
             WHERE j.id = m.journal_id
               AND m.company_id IS NULL
            """,
            table=SQL.identifier(TABLE),
        )
    )
    cr.execute(SQL("SELECT id FROM res_company"))
    companies = cr.fetchall()
    if len(companies) == 1:
        cr.execute(
            SQL(
                "UPDATE %(table)s SET company_id = %(company)s WHERE company_id IS NULL",
                table=SQL.identifier(TABLE),
                company=companies[0][0],
            )
        )
    cr.execute(SQL("SELECT array_agg(id) FROM %(table)s WHERE company_id IS NULL", table=SQL.identifier(TABLE)))
    if missing := cr.fetchone()[0]:
        _logger.warning("Direct debit mandates without company, Odoo requires one: %s", missing)
