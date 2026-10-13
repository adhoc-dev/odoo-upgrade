# Test declarativo de la migración 18->19 de la clave COT de ARBA con sucursales.
#
# base/19.0.0.0/end-migration.py convierte compañías en sucursales y mueve a la padre
# los remitos, pero la clave COT (res.company.arba_cot) queda donde estaba.
# l10n_ar_stock/19.0.0.0/end-migration.py:
#   padre sin clave + sucursal con clave  ->  la padre toma la clave de la sucursal
#   padre con clave                       ->  sin cambios
#   sucursales con claves distintas       ->  sin cambios, aviso en el log
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007). La base llega
# preparada por tests/pre_odu/l10n_ar_stock/180_190/040-cot_key_on_branch.py.

EXPECTED = {
    "res.company": {
        # Rama "padre sin clave": la main company llega sin clave y la migración le
        # cuelga la sucursal sembrada, que tiene "COT-SUCURSAL". Si queda vacía, los
        # remitos que se movieron a la padre no pueden pedir el COT.
        ref("base.main_company"): {
            "arba_cot": "COT-SUCURSAL",
        },
        # Preservación: la sucursal conserva su clave. Si llega vacía, el script la
        # movió en vez de copiarla.
        ref("upgrade_prepare_demo.company_store_to_branch"): {
            "arba_cot": "COT-SUCURSAL",
        },
    },
}
