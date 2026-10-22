"""Reporte de seguimiento de pagos después del salto a 20.

scripts/pre_odoo/190_200/020-followup_report_residual_column.py borra, antes del pase, la
columna de importe residual sin xmlid que agregaba account_accountant_ux en 19. En 20 el
reporte trae la suya (followup_report_amount_residual) y la columna pasa a ser única por
reporte y etiqueta.
"""

EXPECTED = {
    "account.report": {
        # Parte de las columnas nativas de 19 sin la de balance, más la de importe residual sin
        # xmlid que sembró tests/pre_odu/account_reports/190_200 (como la creaba el hook). Tienen
        # que quedar solo las columnas de 20: si sobra una, el pre-odoo no borró la columna sin
        # xmlid; si la carga de los datos de account_reports falló, el -u ni siquiera llega acá.
        ref("account_reports.followup_report"): {
            "column_ids": [
                ref("account_reports.followup_report_follow_up"),
                ref("account_reports.followup_report_invoicing_date"),
                ref("account_reports.followup_report_date_maturity"),
                ref("account_reports.followup_report_amount"),
                ref("account_reports.followup_report_amount_currency"),
                ref("account_reports.followup_report_amount_residual"),
                ref("account_reports.followup_report_amount_residual_currency"),
            ],
        },
    },
}
