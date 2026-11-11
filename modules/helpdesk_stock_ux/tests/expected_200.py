# Test declarativo de modules/helpdesk_stock_ux/20.0.1.0.0/post-migration.py.
#
# La transformacion: helpdesk_stock define helpdesk.ticket.product_id y lot_id hasta 19.0 y
# los saca en 20.0, asi que el pase se lleva las dos columnas. El pre_odoo
# (scripts/pre_odoo/always/130-backup_helpdesk_ticket_product_lot.py) respalda los valores
# antes de mandar la base, helpdesk_stock_ux vuelve a definir los dos campos y el
# post-migration los escribe de nuevo, por id.
#
#   ticket con producto y lote -> el mismo producto y el mismo lote
#   ticket con producto solo   -> el mismo producto, el lote sigue vacio
#   ticket sin ninguno de los dos -> los dos siguen vacios (preservacion)
#
# La siembra es tests/pre_odu/helpdesk_stock_ux/190_200/010-ticket_product_and_lot.py:
# ningun ticket de la data de prueba trae producto ni lote, porque las vistas estandar de 18
# y 19 no los muestran.
#
# Los ref() del lado del valor son la parte que importa: el respaldo viaja con ids, asi que
# un verde aca dice tambien que el pase conservo los ids de product.product y de stock.lot,
# que es lo que no podemos dar por cierto hasta que corra una migracion de prueba.
#
# La rama que falta es la del producto borrado en el pase: ese registro no existe del otro
# lado, no hay ref() que lo apunte y el runner no acepta declarar una ausencia. La cubre
# modules/helpdesk_stock_ux/tests/test_restore_product_and_lot.py.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007).

EXPECTED = {
    "helpdesk.ticket": {
        # Las dos puntas: el ticket tenia producto y lote antes del pase. Si alguno viene
        # vacio, el valor se perdio -- o nunca se respaldo, o el post-migration no corrio.
        ref("upgrade_prepare_demo.hst_ticket_product_and_lot"): {
            "product_id": ref("upgrade_prepare_demo.hst_tracked_product"),
            "lot_id": ref("upgrade_prepare_demo.hst_tracked_lot"),
        },
        # Producto sin lote, que es el caso mas comun en las bases. Un lote aca significaria
        # que el script le invento al ticket la mitad que nunca tuvo.
        ref("upgrade_prepare_demo.hst_ticket_only_product"): {
            "product_id": ref("upgrade_prepare_demo.hst_tracked_product"),
            "lot_id": None,
        },
        # Preservacion: nunca tuvo ninguno de los dos, asi que no entra en el respaldo. Un
        # valor aca seria el script escribiendo sobre tickets que no le tocan.
        ref("upgrade_prepare_demo.hst_ticket_without_product"): {
            "product_id": None,
            "lot_id": None,
        },
    },
}
