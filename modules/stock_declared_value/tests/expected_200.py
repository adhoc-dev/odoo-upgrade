# El post-migration de 20.0.1.0.0 solo lee: lista los tipos de operación que calculan el
# valor declarado con lista de precios y deja el dato para la nota del cliente. No cambia
# ningún registro, así que no hay estado esperado que declarar.
NO_CHECK = (
    "Solo lee y emite el dato de la customer note con add_customer_note; "
    "no modifica registros de la base."
)
