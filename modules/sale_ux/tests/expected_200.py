# sale_ux 19 -> 20 (tarea 76366).
#
# 1. La imagen del producto en el presupuesto: sale_ux.show_product_image_on_report (parametro
#    global de 19) pasa al ajuste nativo de cada compania, res.company.display_product_images_on_so.
#    Migra sale_ux/20.0.0.0/post-migration.py.
# 2. La facturacion forzada (sale.order.force_invoiced_status) se mantiene en sale_ux: el
#    dato tiene que sobrevivir con el mismo estado de facturacion en la orden y en sus lineas
#    y con el monto a facturar de la orden en cero. No migra ningun script: es el check de que el dato
#    no se pierde.
EXPECTED = {
    "res.company": {
        # Rama "ajuste prendido": parte de sale_ux.show_product_image_on_report = 'True'.
        # En 20 el ajuste de la compania nace en False; si queda asi, el script no paso el
        # parametro y las bases que mostraban la imagen la pierden en el presupuesto.
        ref("base.main_company"): {
            "display_product_images_on_so": True,
        },
    },
    "sale.order": {
        # Rama "forzada como facturada": parte de force_invoiced_status = 'invoiced' en una orden
        # confirmada. Si la orden vuelve a "A facturar" o le queda monto a facturar, Odoo propone
        # facturar una orden que el usuario ya habia dado por facturada.
        ref("upgrade_prepare_demo.so_force_invoiced"): {
            "force_invoiced_status": "invoiced",
            "invoice_status": "invoiced",
            "amount_to_invoice": 0.0,
        },
        # Rama "forzada como nada que facturar": parte de force_invoiced_status = 'no'. 20 no
        # tiene equivalente nativo de este estado; si se pierde, la orden vuelve a "A facturar".
        ref("upgrade_prepare_demo.so_force_nothing"): {
            "force_invoiced_status": "no",
            "invoice_status": "no",
            "amount_to_invoice": 0.0,
        },
        # Preservacion: orden confirmada sin forzar. El dato nuevo no tiene que alcanzarla:
        # sigue "A facturar" y sin facturacion forzada.
        ref("upgrade_prepare_demo.so_not_forced"): {
            "force_invoiced_status": None,
            "invoice_status": "to invoice",
        },
    },
    "sale.order.line": {
        # El cierre nativo de 20 solo marca la orden, asi que las lineas son lo que se
        # pierde primero: parte de force_invoiced_status = 'invoiced' en la orden. Si la linea
        # queda "A facturar", la factura se propone por linea. El monto a facturar no se
        # verifica en la linea: sale_ux lo pone en cero solo en la orden (tampoco en 19).
        ref("upgrade_prepare_demo.so_force_invoiced_line"): {
            "invoice_status": "invoiced",
        },
        # Idem con 'no': la linea tiene que quedar en "Nada que facturar".
        ref("upgrade_prepare_demo.so_force_nothing_line"): {
            "invoice_status": "no",
        },
        # Preservacion: linea de una orden sin forzar, sigue "A facturar".
        ref("upgrade_prepare_demo.so_not_forced_line"): {
            "invoice_status": "to invoice",
        },
    },
}
