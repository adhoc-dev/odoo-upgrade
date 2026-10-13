# Test declarativo de la migración 18->19 de la COT de ARBA.
#
# 18.0: l10n_ar_stock (nuestro)  ->  19.0: l10n_ar_stock_ux
#   l10n_ar_stock.arba_cot_enabled        -> l10n_ar_stock_ux.arba_cot_enabled
#   l10n_ar_stock.arba_cot_file_sequence  -> l10n_ar_stock_ux.arba_cot_file_sequence
#
# Nuestro l10n_ar_stock se junta con el de Odoo, que no declara estos registros. Sin
# el renombre de xmlid (scripts/pre_upgrade/180_190/module_changes.json), el -u borra
# el grupo y l10n_ar_stock_ux crea registros nuevos: el grupo vacío y la secuencia en 1.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007). La base llega
# preparada por tests/pre_odu/l10n_ar_stock/180_190/010-cot_enabled.py.

EXPECTED = {
    "res.groups": {
        # La casilla "Usar COT de ARBA?" tildada en 18 (grupo implícito de "Usuario
        # interno") tiene que seguir tildada en 19. Si viene [], el grupo es uno
        # nuevo: el de 18 se borró con sus vínculos y ningún usuario ve la COT.
        ref("l10n_ar_stock_ux.arba_cot_enabled"): {
            "implied_by_ids": [ref("base.group_user")],
        },
    },
    "ir.sequence": {
        # La numeración de la COT sigue desde donde estaba en 18 (42). Si viene en 1,
        # l10n_ar_stock_ux creó una secuencia nueva y la de 18 quedó suelta.
        ref("l10n_ar_stock_ux.arba_cot_file_sequence"): {
            "number_next_actual": 42,
        },
    },
}
