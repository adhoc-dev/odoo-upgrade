import logging

from odoo.tools import SQL
from odoo.upgrade import util

_logger = logging.getLogger(__name__)


# Written by scripts/pre_odoo/190_200/020-backup_partner_arca_activities.py, before the pass.
ACTIVITY_BACKUP_TABLE = "res_partner_arca_activity_bu"


def migrate(cr, version):
    _logger.info("Running post-migration for l10n_ar_edi_ux %s", version)
    _move_invoice_pdf_legend(cr)
    _restore_partner_activities(cr)


def _move_invoice_pdf_legend(cr):
    """Move the invoice PDF legend from our backport to the native field.

    In 19 the module backported odoo/enterprise#102032 as l10n_ar_invoice_pdf_legend_ux
    and stopped reading l10n_ar_edi's l10n_ar_show_withholding_legend. In 20
    l10n_ar_edi brings l10n_ar_invoice_pdf_legend, with the same keys, and the module
    drops its field: its column is removed at the end of the update, after this script.

    Empty values are copied too: the native field must not keep a legend that the
    company had removed in 19, whatever the old boolean says.

    Idempotent: a second run finds both columns equal, or ours already removed.
    """
    if not util.column_exists(cr, "res_company", "l10n_ar_invoice_pdf_legend_ux"):
        _logger.info("No l10n_ar_invoice_pdf_legend_ux column: nothing to move")
        return
    cr.execute(
        SQL(
            """
            UPDATE res_company
               SET l10n_ar_invoice_pdf_legend = l10n_ar_invoice_pdf_legend_ux
             WHERE l10n_ar_invoice_pdf_legend IS DISTINCT FROM l10n_ar_invoice_pdf_legend_ux
            """
        )
    )
    _logger.info("Companies whose invoice PDF legend was moved to the native field: %s", cr.rowcount)


def _restore_partner_activities(cr):
    """Link again the ARCA activities that the pass dropped from the contacts.

    In 20 l10n_ar.arca.activity moves from l10n_ar_reports_simple to l10n_ar. If the pass
    deleted the old records instead of reassigning them, res_partner_arca_activity_rel lost
    its rows by cascade. The backup keeps the activity code, which is unique in both versions.

    Only missing links are added, so it does nothing when the pass kept the records. Codes
    that no longer exist in 20 are logged and dropped. The backup table is removed at the end.
    """
    if not util.table_exists(cr, ACTIVITY_BACKUP_TABLE):
        _logger.info("No %s table: no partner activities to restore", ACTIVITY_BACKUP_TABLE)
        return
    cr.execute(
        SQL(
            """
            INSERT INTO res_partner_arca_activity_rel (partner_id, arca_activity_id)
            SELECT b.partner_id, a.id
              FROM %s b
              JOIN l10n_ar_arca_activity a ON a.code = b.code
              JOIN res_partner p ON p.id = b.partner_id
            ON CONFLICT DO NOTHING
            """,
            SQL.identifier(ACTIVITY_BACKUP_TABLE),
        )
    )
    _logger.info("Partner ARCA activities restored: %s", cr.rowcount)
    cr.execute(
        SQL(
            """
            SELECT array_agg(DISTINCT b.code)
              FROM %s b
             WHERE NOT EXISTS (SELECT 1 FROM l10n_ar_arca_activity a WHERE a.code = b.code)
            """,
            SQL.identifier(ACTIVITY_BACKUP_TABLE),
        )
    )
    missing = cr.fetchone()[0]
    if missing:
        _logger.warning("ARCA activity codes not found in 20.0, dropped from the contacts: %s", missing)
    cr.execute(SQL("DROP TABLE %s", SQL.identifier(ACTIVITY_BACKUP_TABLE)))
