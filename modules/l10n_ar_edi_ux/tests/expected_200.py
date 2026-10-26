# Test declarativo de la migracion 19->20 de la leyenda del PDF de la factura.
#
# l10n_ar_edi_ux/20.0.1.0.0/post-migration.py:
#   l10n_ar_invoice_pdf_legend_ux (backport de 19)  ->  l10n_ar_invoice_pdf_legend (nativo de 20)
#   tambien los vacios: el tilde viejo no revive una leyenda que se habia sacado
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007). La base llega
# preparada por tests/pre_odu/l10n_ar_edi_ux/190_200/010-invoice_pdf_legend_cases.py.

EXPECTED = {
    "res.company": {
        # Rama con leyenda: el valor del backport pasa al nativo. Si queda vacio, la
        # factura A/M de esa company sale sin leyenda.
        ref("upgrade_prepare_demo.company_pdf_legend_cbu"): {
            "l10n_ar_invoice_pdf_legend": "payment_on_informed_cbu",
        },
        # Rama sin leyenda y con el tilde viejo en True (el backport lo dejaba sin
        # leer): tiene que quedar vacio. Si sale con leyenda, el pase o el compute
        # la revivieron y la factura imprime algo que la company habia sacado.
        ref("upgrade_prepare_demo.company_pdf_legend_none"): {
            "l10n_ar_invoice_pdf_legend": False,
        },
    },
}
