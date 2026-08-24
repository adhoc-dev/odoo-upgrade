# Test declarativo de la migración 18->19 de sale_order_type_automation.
#
# sale_order_type_automation invirtió el significado de
# sale.order.type.invoice_validate_domain:
#
#   18.0: invoices.filtered_domain(d)             -> lo que MATCHEA se valida
#   19.0: invoices - invoices.filtered_domain(d)  -> lo que MATCHEA queda en borrador
#
# El script de 19.0.0.0/post-migration.py niega cada dominio guardado para
# preservar el comportamiento que el cliente tenía. Ramas que cubre:
#
#   literal, una condición      -> De Morgan del leaf
#   literal, AND implícito      -> '|' de las dos condiciones negadas
#   literal, '|' explícito      -> '&' de las dos condiciones negadas
#   literal ya negado           -> se le saca el '!'
#   con expresión dinámica      -> negación TEXTUAL, expresión intacta
#   vacío / '[]' / no parseable -> sin cambios (preservación)
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que
# recibimos se da por buena. Los registros con dominio llegan por xmlid desde
# la siembra de este mismo repo
# (testing_pre_odu/sale_order_type_automation/180_190/010-invoice_validate_domain_cases.py);
# el caso de preservación sin dominio ancla en la demo del propio módulo.
#
# Cada caso lleva su comentario de QUÉ verifica: la rama de la transformación,
# el valor de partida y por qué ese resultado es el correcto.

EXPECTED = {
    "sale.order.type": {
        # Rama literal de una sola condición: De Morgan sobre el leaf. Parte de
        # [('move_type', '=', 'out_invoice')] — "validar solo las facturas de
        # cliente". En 19 tiene que dejar en borrador todo lo que NO sea factura
        # de cliente, o sea el operador del leaf invertido. Es el caso que anda
        # bien hasta con una negación ingenua, así que por sí solo no prueba
        # gran cosa: está para fijar la forma que se espera del resultado.
        ref("upgrade_prepare_demo.sot_ivd_single"): {
            "invoice_validate_domain": "[('move_type', '!=', 'out_invoice')]",
        },
        # EL CASO CRÍTICO. Dos condiciones con AND implícito. Envolver el
        # dominio en ['!', ...] daría ['!', c1, c2], que en notación polaca es
        # NOT(c1) AND c2 — un dominio distinto, y el error no se ve: sigue
        # siendo un dominio válido. Lo correcto es De Morgan, o sea '|' de las
        # dos negadas. Si acá aparece algo que arranca con '!', el script volvió
        # a la negación ingenua.
        ref("upgrade_prepare_demo.sot_ivd_implicit_and"): {
            "invoice_validate_domain": (
                "['|', ('move_type', '!=', 'out_invoice'), '!', ('amount_total', '>', 100)]"
            ),
        },
        # Operador explícito: negar un OR da un AND. Parte de
        # ['|', c1, c2]; si el resultado conservara el '|', el dominio migrado
        # dejaría en borrador de más (matchearía con una sola condición en vez
        # de las dos).
        ref("upgrade_prepare_demo.sot_ivd_explicit_or"): {
            "invoice_validate_domain": (
                "['&', ('move_type', '!=', 'out_invoice'), '!', ('amount_total', '>', 100)]"
            ),
        },
        # Doble negación. Parte de ['!', c1], un dominio que el cliente puede
        # haber escrito así en 18. Negarlo es sacarle el '!', no agregarle otro.
        # Verifica de paso que el script NO use "empieza con '!'" como señal de
        # "esto ya lo migré": este registro es legítimo y hay que darlo vuelta
        # igual que a los demás.
        ref("upgrade_prepare_demo.sot_ivd_already_negated"): {
            "invoice_validate_domain": "[('move_type', '=', 'out_invoice')]",
        },
        # Expresión dinámica. El campo se renderiza con allow_expressions=True,
        # así que puede tener context_today() o relativedelta(...). El script
        # tiene que negarlo SIN evaluarlo: si acá aparece una fecha concreta en
        # vez de la llamada, alguien metió un safe_eval y le congeló al cliente
        # la ventana de facturación en la fecha de la migración.
        ref("upgrade_prepare_demo.sot_ivd_dynamic"): {
            "invoice_validate_domain": "['!', ('invoice_date', '>=', context_today())]",
        },
        # Preservación: valor que no parsea. Queda intacto; en una base real el
        # script loguea un WARNING para revisión manual, pero sobre este caso
        # sembrado (xmlid de upgrade_prepare_demo) baja a INFO — el warning es
        # la señal para el operador con datos reales, y acá pintaría 'warn'
        # cada corrida del e2e. Si acá apareciera algo modificado, el script
        # estaría escribiendo sobre un valor que no entendió.
        ref("upgrade_prepare_demo.sot_ivd_unparseable"): {
            "invoice_validate_domain": "[('move_type', '=',",
        },
        # Preservación: el dominio vacío literal. En las dos versiones significa
        # "validar todo", así que NO se toca. Es la trampa más cara de esta
        # migración: '[]' es truthy como Char, y negarlo daría [(0, '=', 1)], un
        # dominio que no matchea nada — o sea el cliente dejaría de validar
        # absolutamente todas sus facturas, en silencio.
        ref("upgrade_prepare_demo.sot_ivd_empty_list"): {
            "invoice_validate_domain": "[]",
        },
        # Preservación: tipo con automatización de factura y SIN dominio (NULL).
        # Es el caso más común en bases reales, y verifica que el script no le
        # invente un dominio a quien no tenía ninguno — el falso positivo más
        # probable. Sembrado como los demás: la versión anterior anclaba en la
        # demo del propio módulo y el -u del pipeline (demo apagada) purga esos
        # xmlids en _process_end — el ancla desaparecía post-migración (FAIL
        # real en el build 105875, 24/08).
        ref("upgrade_prepare_demo.sot_ivd_no_domain"): {
            "invoice_validate_domain": None,
        },
    },
}
