# Test declarativo de la migración 18->19 del valor en moneda de stock_currency_valuation.
#
# 18.0: stock.valuation.layer.value_in_currency, una capa por movimiento más las de costo en
#       destino y diferencia de precio, que cuelgan de la capa del movimiento.
# 19.0: stock.move.value_in_currency, la suma de esas capas en positivo. stock.move.value, en
#       pesos, tiene que cerrar con la misma regla: stock_currency_valuation de 19 le resta los
#       costos en destino para sacar la base. Por eso cada movimiento verifica los dos valores:
#       si solo cierra la moneda, el valor en moneda no se corresponde con el de pesos.
#
# El pase borra las capas. Lo carga modules/stock_currency_valuation/19.0.0.0/post-migration.py
# desde el respaldo que deja scripts/pre_odoo/180_190/060-backup_currency_valuation_layers.py.
#
# Solo entran los casos con cotización manual o costo en moneda fijo: con cotización
# automática el valor depende de la cotización de la base el día de la siembra. Las
# revalorizaciones tampoco entran: el pase las convierte en product.value, que nace sin xmlid.
#
# Los registros llegan por xmlid desde la siembra de
# tests/pre_odu/stock_currency_valuation/180_190/010-currency_layers_cases.py.

EXPECTED = {
    "stock.move": {
        # Entrada con cotización manual en el remito y un costo en destino con la suya: 10 u a
        # USD 100 más ARS 150.000 / 1.480. Verifica la suma de la capa del movimiento con la del
        # costo en destino; si viene 1000.0, el costo en destino no se sumó. En pesos, ARS
        # 1.450.000 de la capa más 150.000 del costo en destino; si viene 1450000.0, el pase
        # dejó solo la capa propia.
        ref("upgrade_prepare_demo.scv_c02_move_in"): {
            "value": 1600000.0,
            "value_in_currency": 1101.35,
        },
        # Entrada simple con cotización manual: 10 u a USD 100 a 1.450, una sola capa. Si viene
        # 0.0, el respaldo no llegó o el movimiento no se encontró.
        ref("upgrade_prepare_demo.scv_c03_move_in"): {
            "value": 1450000.0,
            "value_in_currency": 1000.0,
        },
        # Entrada de la compra que después se devuelve en parte: queda con su valor entero, la
        # devolución es otro movimiento. Si viene 600.0 (o 870000.0 en pesos), se mezclaron los
        # dos movimientos.
        ref("upgrade_prepare_demo.scv_c09_move_in"): {
            "value": 1450000.0,
            "value_in_currency": 1000.0,
        },
        # Devolución a proveedor de 4 u al costo de la entrada (ARS 145.000 y USD 100 por
        # unidad): en 18 la capa es negativa y en 19 el valor va en positivo. Si viene -400.0 o
        # -580000.0, faltó pasar el signo al de 19.
        ref("upgrade_prepare_demo.scv_c09_move_return"): {
            "value": 580000.0,
            "value_in_currency": 400.0,
        },
        # Entrega de una venta, 5 u al costo del producto (ARS 150.000 y USD 100). Rama de
        # salida.
        ref("upgrade_prepare_demo.scv_c10_move_out"): {
            "value": 750000.0,
            "value_in_currency": 500.0,
        },
        # Devolución del cliente, 2 u al costo de la entrega original. Rama de entrada que sale
        # de una devolución.
        ref("upgrade_prepare_demo.scv_c11_move_return"): {
            "value": 300000.0,
            "value_in_currency": 200.0,
        },
        # Preservación: producto sin moneda de valuación, compra en USD. Tiene que quedar sin
        # valor en moneda; si viene 1000.0, el script le cargó el importe de la compra a un
        # producto que no se valúa en moneda. El valor en pesos no entra: la compra va con la
        # cotización automática de la base.
        ref("upgrade_prepare_demo.scv_c17_move_in"): {
            "value_in_currency": 0.0,
        },
        # Ingreso de importación con tres productos y tres costos en destino de varias líneas,
        # repartidos por cantidad sobre 20 u (ARS 10.000 por unidad). En pesos: la capa de cada
        # movimiento a 1.450 más su parte de los costos en destino. Si viene solo la capa
        # (1450000.0, 1450000.0 y 362500.0), el pase no sumó los costos en destino.
        ref("upgrade_prepare_demo.scv_c18_move_in"): {
            "value": 1550000.0,
        },
        ref("upgrade_prepare_demo.scv_c18b_move_in"): {
            "value": 1500000.0,
        },
        ref("upgrade_prepare_demo.scv_c18c_move_in"): {
            "value": 412500.0,
        },
    },
}
