import logging

_logger = logging.getLogger(__name__)

# Caso de scripts/pre_odoo/190_200/020-followup_report_residual_column.py, que antes del pase
# borra del reporte de seguimiento la columna de importe residual sin xmlid. Lo verifica
# account_reports/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la columna la crea el post_init_hook de account_accountant_ux en 19,
# y la base canonica no la tiene si el modulo no estaba instalado cuando se armo. Se siembra
# igual que la creaba el hook: sin xmlid, en lugar de la columna de balance. Sin xmlid a
# proposito: es lo que distingue a la columna del hook de la nativa de 20, y es lo que el
# script busca. Por eso no va con _load_records.


def migrate(env):
    report = env.ref("account_reports.followup_report", raise_if_not_found=False)
    if not report:
        _logger.info("account_reports.followup_report is not in this database - not seeding it")
        return
    # Idempotente: si ya esta (la sembro una corrida anterior o el hook), no se duplica.
    if report.column_ids.filtered(lambda column: column.expression_label == "amount_residual"):
        return
    report.column_ids.filtered(lambda column: column.expression_label == "balance").unlink()
    env["account.report.column"].create(
        {
            "name": "Amount Residual",
            "expression_label": "amount_residual",
            "figure_type": "monetary",
            "report_id": report.id,
            "sequence": 100,
        }
    )
