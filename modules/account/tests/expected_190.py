# Test declarativo de scripts/pre_upgrade/180_190/unfavorite_unused_purchase_journals.py.
#
# La transformacion: un diario de compras que es favorito (show_on_dashboard), se creo hace
# mas de un ano y no tiene ningun asiento deja de ser favorito. Los tres filtros (tipo,
# antiguedad, asientos) solo seleccionan registros; el valor es siempre False, asi que entra
# en el carril declarativo. Todos los casos parten de show_on_dashboard = True y los siembra
# tests/pre_odu/account/180_190/010-unused_purchase_journal_cases.py.

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
}
