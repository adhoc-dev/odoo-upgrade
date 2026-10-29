# Test declarativo de purchase_stock_ux/20.0.1.0.0/pre-migration.py.
#
# La transformacion: hasta 19 el modulo le fijaba el proveedor a las reglas de
# reabastecimiento que crea Odoo solo. En 20 la regla sigue al proveedor
# principal mientras no tenga uno fijo, asi que el script se lo saca a esas.
#
#   creada por OdooBot, disparador manual      -> sin proveedor
#   creada por una persona, disparador manual  -> conserva el suyo (preservacion)
#   creada por OdooBot, disparador automatico  -> conserva el suyo (preservacion)
#
# Las tres reglas las siembra tests/pre_odu/purchase_stock_ux/190_200/
# 010-orderpoint_supplier_cases.py: la demo de 19 no trae reglas.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "stock.warehouse.orderpoint": {
        # Rama que cambia: la creo OdooBot con disparador manual y tiene el
        # proveedor que le fijo el modulo en 19. Si lo conserva, el script no
        # corrio y la regla no va a seguir al proveedor principal en 20.
        ref("upgrade_prepare_demo.op_supplier_odoobot_manual"): {
            "supplier_id": None,
        },
        # Preservacion: la cargo una persona con disparador manual. Si queda
        # vacia, el script borro un proveedor que eligio alguien a mano.
        ref("upgrade_prepare_demo.op_supplier_person_manual"): {
            "supplier_id": ref("upgrade_prepare_demo.op_supplier_info_person_manual"),
        },
        # Preservacion: la creo OdooBot pero tiene disparador automatico, o sea
        # que alguien la dejo como regla fija. Si queda vacia, el script no
        # filtro por el disparador.
        ref("upgrade_prepare_demo.op_supplier_odoobot_auto"): {
            "supplier_id": ref("upgrade_prepare_demo.op_supplier_info_odoobot_auto"),
        },
    },
}
