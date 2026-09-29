import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Alinea receipt_status con force_delivered_status en purchase_order (por SQL).

    El pre-migration ya remapeó force_delivered_status al vocabulario de la v19
    ('no' -> NULL, 'to receive' -> 'pending', 'received' -> 'full'). En la v19 el force
    gobierna el receipt_status nativo (ver purchase_stock_ux._compute_receipt_status:
    receipt_status = force_delivered_status cuando el force está seteado), pero
    receipt_status es un campo stored computed: ni el -u ni un UPDATE por SQL disparan
    su recompute.

    En lugar de recomputar por ORM (util.recompute_fields corre el compute registro por
    registro en Python, costoso con muchas OC), replicamos la lógica del override con un
    UPDATE set-based: donde hay force, receipt_status = force_delivered_status. Las OC sin
    force conservan el valor nativo (picking-driven) que ya venía calculado desde v17/v18.
    """
    _logger.info(
        "Alineando receipt_status con force_delivered_status en purchase_order"
    )

    # force_delivered_status ya está en el vocabulario v19 (pending/full) o NULL, y esos
    # valores son válidos para receipt_status. Idempotente: solo toca filas desalineadas.
    cr.execute(
        """
        UPDATE purchase_order
           SET receipt_status = force_delivered_status
         WHERE force_delivered_status IS NOT NULL
           AND receipt_status IS DISTINCT FROM force_delivered_status
        """
    )
    _logger.info("Se actualizaron %d registros en purchase_order", cr.rowcount)
