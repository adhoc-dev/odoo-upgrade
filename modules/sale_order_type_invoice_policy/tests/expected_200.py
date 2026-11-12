# sale_order_type_invoice_policy 19 -> 20 (tarea 76458).
#
# services_delivered vivio en este modulo entre el 13/05 y el 28/09 de 2026, cuando paso al
# bridge sale_order_type_invoice_policy_project (depende de sale_project). El traspaso del
# xmlid lo hacia migrations/19.0.1.2.0/pre-migration.py del propio modulo, y al migrar el
# modulo a 20 esa carpeta se borra (ADR 0050 de actua-20): una base que salta a 20 desde un
# 19 anterior al 28/09 llega con el xmlid apuntando al modulo padre, que en 20 ya no declara
# el campo. Reproducido sobre una base 20 en ese estado: el bridge no se auto-instala en el
# -u, se borra field_sale_order_type__services_delivered con su columna y el dato se pierde.
# Es lo que anticipaba el comentario del pre-migration de 19.0.1.2.0.
#
# Ese estado no existe en ningun cliente, asi que no hay nada que verificar: el motivo de
# abajo lo dice con los numeros con que se comprobo.
NO_CHECK = (
    "El unico estado que pierde services_delivered es una base de 19 anterior al 28/09/2026, "
    "con el xmlid del campo todavia en el modulo padre y el bridge sin instalar, y no queda "
    "ninguna: de las 31 bases productivas activas de 19 con el modulo, las 16 que tienen "
    "sale_project ya tienen el bridge instalado (pasaron por 19.0.1.2.0) y las otras 15 no "
    "tienen sale_project, asi que el caso no les aplica (saas.database.module_ids, 12/11/2026). "
    "Un check pedia sembrar un estado que ninguna base real tiene."
)
