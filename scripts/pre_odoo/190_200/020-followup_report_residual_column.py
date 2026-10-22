import logging

from oba import log_message, should_run_pre_odoo

_logger = logging.getLogger(__name__)

FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20


def migrate(cr, version):
    """Drop the residual column we added to the follow-up report before the database is sent to Odoo.

    account_accountant_ux (and account_followup_ux before it, in 18.0) replaced the balance
    column of account_reports.followup_report with a column of its own, without xmlid, on
    the expression "amount_residual". In 20.0 the report brings its own
    followup_report_amount_residual column, and account.report.column gets
    unique(report_id, expression_label): loading account_reports/data/followup_report.xml
    fails with a UniqueViolation. That load runs in Odoo's upgrade, so after the pass is too
    late. The migrated account_accountant_ux does not add the column anymore.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_run_pre_odoo(cr, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=["account_reports"]):
        return

    cr.execute(
        """
        DELETE FROM account_report_column c
         USING ir_model_data report
         WHERE report.module = 'account_reports'
           AND report.name = 'followup_report'
           AND report.model = 'account.report'
           AND c.report_id = report.res_id
           AND c.expression_label = 'amount_residual'
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data d
                 WHERE d.model = 'account.report.column'
                   AND d.res_id = c.id
           )
     RETURNING c.id
        """
    )
    dropped = sorted(row[0] for row in cr.fetchall())
    if dropped:
        _logger.info("Dropped the residual columns without xmlid of the follow-up report: %s", dropped)
        log_message(
            cr,
            "Se borró del reporte de seguimiento la columna de importe residual que agregaba "
            "account_accountant_ux (ids %s): en 20.0 la trae el reporte nativo." % dropped,
            "info",
        )
