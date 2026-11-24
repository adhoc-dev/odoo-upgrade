# Test declarativo de modules/account_ux/20.0.1.0.0/post-migration.py.
#
# La transformacion: en 20, account_ux suma expense_other a los tipos de cuenta
# no monetarios. is_monetary se guarda, asi que las cuentas que vienen de 19 no se
# recalculan y el script las corrige:
#
#   expense_other monetaria  -> no monetaria
#   otro tipo                -> sin cambios (preservacion)
#
# Las cuentas las siembra tests/pre_odu/account_ux/190_200/010-is_monetary_cases.py.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007).

EXPECTED = {
    "account.account": {
        # Rama "expense_other": en 19 nacio monetaria por su tipo. Si sigue en True,
        # el revaluo la toma al tipo de cambio de cierre en vez del historico.
        ref("upgrade_prepare_demo.account_is_monetary_other_expense"): {
            "is_monetary": False,
        },
        # Preservacion: una cuenta de activo corriente es monetaria y tiene que
        # seguir asi. Si queda en False, el script toco cuentas de otro tipo.
        ref("upgrade_prepare_demo.account_is_monetary_current_asset"): {
            "is_monetary": True,
        },
    },
}
