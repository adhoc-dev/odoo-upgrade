# Test declarativo de sale_stock_ux/20.0.1.0.0/post-migration.py en el salto a 20.
#
# La transformacion: recalcula sale.order.line.delivery_status en las lineas de
# ventas confirmadas que tienen guardado 'no' (el default con que quedaron las
# lineas que ya existian al instalar el modulo).
#
#   guardada en 'no', con algo para entregar   -> 'to deliver'
#   guardada en 'no', venta forzada a 'no'      -> 'no' (preservacion)
#
# La siembra (tests/pre_odu/sale_stock_ux/190_200/010-stale_delivery_status.py)
# deja las dos lineas con 10 pedidas, nada entregado y 'no' guardado por SQL.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007).

EXPECTED = {
    "sale.order.line": {
        # Rama del recalculo: partia de 'no' con 10 unidades sin entregar. Si
        # sigue en 'no', el script no la recalculo y la venta no aparece en el
        # filtro "To Deliver" ni en la tarjeta del tablero.
        ref("upgrade_prepare_demo.sol_stale_to_deliver"): {
            "delivery_status": "to deliver",
        },
        # Preservacion: partia de 'no' y la venta esta forzada a "Nada para
        # entregar". Si pasa a 'to deliver', el recalculo ignoro el forzado.
        ref("upgrade_prepare_demo.sol_stale_forced_no"): {
            "delivery_status": "no",
        },
    },
}
