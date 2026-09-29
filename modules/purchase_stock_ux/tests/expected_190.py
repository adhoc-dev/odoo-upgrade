# Test declarativo de la migración 18->19 de purchase_stock_ux.
# Cobertura del remapeo de force_delivered_status (misma que el PR #172):
#
# 18.0: ('no', 'received')  ->  19.0: ('pending', 'partial', 'full')
#   'no'        -> vacío (NULL)
#   'received'  -> 'full'
#   NULL / otro -> sin cambios (preservación)
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que
# recibimos se da por buena. Los registros llegan por xmlid desde la inyección
# de upgrade-prepare-demo
# (purchase_stock_ux/180_190/010-force_delivered_status_cases.py).
#
# Cada caso lleva su comentario de QUÉ verifica: la rama de la transformación,
# el valor de partida y por qué ese resultado es el correcto.

EXPECTED = {
    "purchase.order": {
        # Rama 'no': el valor dejó de existir en el selection de 19, así que el
        # script tiene que vaciarlo. Parte de force_delivered_status = 'no';
        # si quedara algo, el remapeo dejó un valor inválido para 19.
        ref("upgrade_prepare_demo.po_force_delivered_no"): {
            "force_delivered_status": None,
        },
        # Rama 'received': equivale al 'full' de 19 (entregado por completo).
        # Parte de 'received'; es el único caso que cambia de valor en vez de
        # vaciarse, y verifica que el mapeo no lo confunda con 'partial'.
        ref("upgrade_prepare_demo.po_force_delivered_received"): {
            "force_delivered_status": "full",
        },
        # Rama de preservación: la PO nunca tuvo el forzado seteado (NULL) y
        # tiene que seguir así. Verifica que el script no le invente un estado
        # a los registros que no pasan por el remapeo — el falso positivo más
        # probable de este tipo de migración.
        ref("upgrade_prepare_demo.po_force_delivered_null"): {
            "force_delivered_status": None,
        },
    },
}
