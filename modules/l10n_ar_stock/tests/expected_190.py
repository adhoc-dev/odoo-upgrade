# Test declarativo de la migración 18->19 de l10n_ar_stock.
#
# (1) Clave COT de ARBA con sucursales. base/19.0.0.0/end-migration.py convierte compañías en
# sucursales y mueve a la padre los remitos, pero la clave COT (res.company.arba_cot) queda
# donde estaba. l10n_ar_stock/19.0.0.0/end-migration.py:
#   padre sin clave + sucursal con clave  ->  la padre toma la clave de la sucursal
#   padre con clave                       ->  sin cambios
#   sucursales con claves distintas       ->  sin cambios, aviso en el log
#
# (2) Campos que cambian de módulo dueño (dispatch_number, cot, arba_code, …). En 18 los
# declara l10n_ar_stock (Adhoc) sobre modelos de Odoo; en 19 ese nombre lo toma el módulo de
# Odoo y el pase borra las columnas, que l10n_ar_stock_ux recrea vacías. El end-migration las
# repone desde el respaldo de scripts/pre_odoo/180_190/070-backup_l10n_ar_stock_fields.py.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007). La base llega preparada por
# tests/pre_odu/l10n_ar_stock/180_190/040-cot_key_on_branch.py y 050-dispatch_number_cases.py.

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
    "stock.lot": {
        # El lote conserva su número de despacho al pasar a 19. Si llega vacío, el pase
        # borró la columna y el restore no lo repuso.
        ref("upgrade_prepare_demo.lot_with_dispatch"): {
            "dispatch_number": "DESP-LOTE-18",
        },
        # Control: el lote sin despacho sigue sin despacho. Si llega con número, el restore
        # pisó registros que no estaban en el respaldo.
        ref("upgrade_prepare_demo.lot_without_dispatch"): {
            "dispatch_number": False,
        },
    },
    "stock.picking": {
        # El remito conserva despacho y cot al pasar a 19 (respaldo multi-columna).
        ref("upgrade_prepare_demo.picking_with_dispatch"): {
            "dispatch_number": "DESP-REMITO-18",
            "cot": "COT-REMITO-18",
        },
    },
    "product.product": {
        # El producto conserva su arba_code (campo de product.template) al pasar a 19.
        ref("upgrade_prepare_demo.product_dispatch"): {
            "arba_code": "180190",
        },
    },
}
