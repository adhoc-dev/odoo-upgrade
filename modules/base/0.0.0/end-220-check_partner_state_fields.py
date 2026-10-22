"""Tell the customer which partner_state configuration lines the upgrade removed.

Reads what scripts/pre_odoo/always/220-backup_partner_state_fields.py backed up on the old
database. A line is lost when the upgrade drops its res.partner field (ON DELETE CASCADE):
already gone when this runs, or about to go, because no loaded module defines its field
any more and _process_end and end-900 drop it after the end- scripts.
Only a report: which field replaces it, if any, is decided by hand.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import add_customer_note, log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "res_partner_state_field_bu"
FIRST_TARGET_VERSION = 20


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["partner_state"]):
        return
    run(cr, set(util.env(cr)["res.partner"]._fields))


def run(cr, partner_fields):
    """:param partner_fields: the res.partner fields the loaded code defines"""
    if not util.table_exists(cr, BACKUP_TABLE):
        # Not "nothing was lost": nobody looked. Emitting zero would say all is fine.
        _logger.warning("No %s: the partner state fields were not checked. Did the pre_odoo run?", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            SELECT bu.field_name, bu.field_label, bu.approval, bu.block_edition, bu.track, bu.changes
              FROM %s bu
              LEFT JOIN res_partner_state_field s ON s.id = bu.id
              LEFT JOIN ir_model_fields f ON f.id = s.field_id
             WHERE s.id IS NULL
                OR NOT f.name = ANY(%s)
             ORDER BY bu.field_name
            """,
            SQL.identifier(BACKUP_TABLE),
            sorted(partner_fields),
        )
    )
    lost = [
        {
            "campo": name,
            "etiqueta": label,
            "requerido_para_aprobar": bool(approval),
            "bloqueado_si_aprobado": bool(block_edition),
            "vuelve_a_potencial": bool(track),
            "registra_en_chatter": bool(changes),
        }
        for name, label, approval, block_edition, track, changes in cr.fetchall()
    ]
    # Also with no rows: the table was there, so "nothing was lost" is a result.
    add_customer_note(
        cr,
        {
            "partner_state_campos_perdidos": lost,
            "partner_state_campos_perdidos_total": len(lost),
        },
    )
    if lost:
        log_message(
            cr,
            "partner_state: %s configuration lines lost their field in the upgrade: %s"
            % (len(lost), [line["campo"] for line in lost]),
            "warning",
        )
