# product_replenishment_cost 19 -> 20 (tarea 76406).
#
# post-migration.py no cambia datos del cliente: evalua las expresiones de las reglas de costo
# de reposicion y deja con add_customer_note las que fallan, para la nota del pase.
NO_CHECK = (
    "No escribe en la base del cliente: solo emite el dato de la customer note con "
    "add_customer_note, y este carril verifica el estado de los modelos, no esa tabla. Se probo "
    "sobre una base 20 con una regla de cinco lineas: reporto las tres que fallan (product_uom_id "
    "de la linea de proveedor, _select_seller y una expresion '$'), no la que evalua bien, y "
    "salteo la regla que ningun producto usa."
)
