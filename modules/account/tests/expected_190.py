# Test declarativo de scripts/pre_upgrade/180_190/unfavorite_unused_purchase_journals.py.
#
# La transformacion: un diario de compras que es favorito (show_on_dashboard), se creo hace
# mas de un ano y no tiene ningun asiento deja de ser favorito. Los tres filtros (tipo,
# antiguedad, asientos) solo seleccionan registros; el valor es siempre False, asi que entra
# en el carril declarativo. Todos los casos parten de show_on_dashboard = True y los siembra
# tests/pre_odu/account/180_190/010-unused_purchase_journal_cases.py.
#
# Tambien el de scripts/pre_upgrade/180_190/account_payment_provider_single_method_line.py:
# un proveedor con lineas electronicas en dos diarios se queda con la del pago mas
# reciente, y las demas pasan al metodo manual sin proveedor. Lo siembra
# tests/pre_odu/account/180_190/020-payment_provider_duplicate_lines.py.

EXPECTED = {
    "account.journal": {
        # Rama que cambia: compras, favorito, de hace 400 dias y sin asientos. Si sigue
        # en True, el script no corrio o su filtro dejo afuera un diario que cumple todo.
        ref("upgrade_prepare_demo.journal_purchase_old_unused"): {
            "show_on_dashboard": False,
        },
        # Preservacion por asientos: igual al anterior pero con un asiento. Si queda en
        # False, el script le saco el favorito a un diario en uso (falta el NOT EXISTS).
        ref("upgrade_prepare_demo.journal_purchase_old_used"): {
            "show_on_dashboard": True,
        },
        # Preservacion por antiguedad: compras, sin asientos, pero recien creado. Si queda
        # en False, el script ignora el limite de un ano.
        ref("upgrade_prepare_demo.journal_purchase_recent_unused"): {
            "show_on_dashboard": True,
        },
        # Preservacion por tipo: de ventas, de hace 400 dias y sin asientos. Si queda en
        # False, el script se paso del tipo purchase.
        ref("upgrade_prepare_demo.journal_sale_old_unused"): {
            "show_on_dashboard": True,
        },
    },
    "account.payment.method.line": {
        # Rama que cambia: la linea con el pago mas viejo del proveedor. Si conserva el
        # proveedor, el script no corrio o eligio mal cual queda.
        ref("upgrade_prepare_demo.payment_method_line_old"): {
            "payment_method_id": ref("account.account_payment_method_manual_in"),
            "payment_provider_id": None,
        },
        # Preservacion: la linea con el pago mas reciente sigue con el proveedor. Si queda
        # vacio, el script paso a manual todas las lineas.
        ref("upgrade_prepare_demo.payment_method_line_recent"): {
            "payment_provider_id": ref("upgrade_prepare_demo.payment_provider_two_lines"),
        },
        # Preservacion por metodo: ya era manual y tiene el proveedor. Si lo pierde, el
        # script conto una linea que la 19 no cuenta.
        ref("upgrade_prepare_demo.payment_method_line_manual"): {
            "payment_method_id": ref("account.account_payment_method_manual_in"),
            "payment_provider_id": ref("upgrade_prepare_demo.payment_provider_two_lines"),
        },
    },
    "account.payment": {
        # El pago de la linea que cambia acompana su metodo. Si sigue con el electronico,
        # el metodo del pago no coincide con el de su linea.
        ref("upgrade_prepare_demo.payment_payment_method_line_old"): {
            "payment_method_id": ref("account.account_payment_method_manual_in"),
        },
    },
}
