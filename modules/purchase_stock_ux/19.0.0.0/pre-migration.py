import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Ajuste en force_delivered_status para purchase_order.
    Se ejecuta antes de la actualización del módulo para asegurar que los datos
    sean compatibles con la nueva lógica de la v19.
    """
    _logger.info(
        "Iniciando pre-migración para ajustar force_delivered_status en purchase_order"
    )

    # Nuevo mapeo de estados
    # 'no' -> NULL
    # 'to receive' -> 'pending'
    # 'received' -> 'full'

    query = """
        UPDATE purchase_order
        SET force_delivered_status = CASE 
            WHEN force_delivered_status = 'no' THEN NULL
            WHEN force_delivered_status = 'to receive' THEN 'pending'
            WHEN force_delivered_status = 'received' THEN 'full'
            ELSE force_delivered_status
        END
        WHERE force_delivered_status IN ('no', 'to receive', 'received');
    """

    cr.execute(query)
    _logger.info("Se actualizaron %d registros en purchase_order", cr.rowcount)
