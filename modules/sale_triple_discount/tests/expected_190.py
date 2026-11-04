# Test declarativo del salto 18->19 de los descuentos de factura de sale_three_discounts.
#
# En 18 sale_three_discounts guarda discount1/2/3 en account.move.line y discount es la
# combinación. En 19 se fusiona en sale_triple_discount, que instala
# account_invoice_triple_discount, y su post_init_hook hace discount1 = discount y
# recalcula discount con los tres. Lo evitan
# scripts/pre_upgrade/180_190/account_invoice_triple_discount_keep_discounts.py y
# modules/base/19.0.0.0/end-account_invoice_triple_discount_restore_discounts.py.
#
# Las líneas salen de tests/pre_odu/sale_triple_discount/180_190/010-invoice_line_discounts.py.

EXPECTED = {
    "account.move.line": {
        # Dos descuentos, 10 y 20. Si el hook corrió sin el respaldo, discount1 queda en 28
        # (el combinado) y el 20 se aplica dos veces.
        ref("upgrade_prepare_demo.aml_two_discounts"): {
            "discount1": 10.0,
            "discount2": 20.0,
            "discount3": 0.0,
        },
        # Descuento de 676,28 guardado solo en discount. Es el caso que cortaba el -u
        # contra CHECK (discount1 <= 100). Tiene que llegar igual: si discount quedó en 0,
        # el script no restauró; si discount1 tiene el valor, el hook lo copió.
        ref("upgrade_prepare_demo.aml_discount_over_100"): {
            "discount": 676.28,
            "discount1": 0.0,
        },
    },
}
