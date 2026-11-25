# stock_request 19 -> 20: pre-migration.py and post-recalculated_total.py only count how many
# requests the post-migration.py of OCA recomputed, and leave the total for the customer note of
# the upgrade line 2751.
NO_CHECK = (
    "Los scripts no cambian datos: copian qty_done antes del -u y cuentan las solicitudes que "
    "cambiaron, para el customer note. Lo que hay que verificar es el valor que queda en "
    "oba_upgrade_customer_note, que no es un modelo y este carril no lo lee. Lo cubre "
    "modules/stock_request/tests/test_recalculated_total.py, que corre los dos scripts contra "
    "su propia base."
)
