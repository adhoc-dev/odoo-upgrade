# Test declarativo de la migracion 19->20 del proveedor de cotizacion ARCA.
#
# l10n_ar_currency_update/20.0.1.0.0/pre-migration.py:
#   currency_provider = 'afip'   ->  'arca' (el nativo de l10n_ar_edi en 20)
#   otro proveedor               ->  sin cambios
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007). La base llega
# preparada por tests/pre_odu/l10n_ar_currency_update/190_200/010-currency_provider_cases.py.

EXPECTED = {
    "res.company": {
        # Rama 'afip' -> 'arca': parte de 'afip', que en 20 ningun modulo define.
        # Si queda 'afip', la company no tiene proveedor y deja de actualizar la
        # cotizacion. El % y el recargo siguen siendo del modulo y no se tocan: si
        # cambian, la cotizacion de esa company sale distinta que en 19.
        ref("upgrade_prepare_demo.company_currency_afip"): {
            "currency_provider": "arca",
            "rate_perc": 0.05,
            "rate_surcharge": 1.5,
        },
        # Preservacion: parte de 'ecb' y tiene que seguir asi. Si cambia, el script
        # toco companies que no usaban ARCA.
        ref("upgrade_prepare_demo.company_currency_ecb"): {
            "currency_provider": "ecb",
        },
    },
}
