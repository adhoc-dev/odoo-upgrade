# Test declarativo de la migración 19->20 de sale_order_type_automation.
#
# sale.order.type guarda dos dominios en un Char: invoice_validate_domain (contra
# account.move) y sale_order_filter_domain (contra sale.order). La automatización los
# evalúa con safe_eval al confirmar un pedido, sin try. Odoo 20 rechaza con ValueError lo
# que 19 aceptaba con un aviso de deprecación, así que un tipo con alguno de esos
# operadores no deja confirmar pedidos:
#
#   '<>'  -> '!='
#   '=='  -> '='
#   operador en mayúsculas ('ILIKE') -> en minúsculas
#
# El script de 20.0.0.0/post-migration.py reescribe el operador en el texto, sin evaluar
# el dominio ni tocar el resto. Un campo que 20 ya no tiene (checked, require_payment, ...)
# no tiene equivalente: el script no lo toca y lo reporta a la nota del cliente.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que recibimos se
# da por buena. Los registros llegan por xmlid desde la siembra de este mismo repo
# (tests/pre_odu/sale_order_type_automation/190_200/010-saved_domain_cases.py).
#
# Cada caso lleva su comentario de QUÉ verifica: la rama de la transformación, el valor de
# partida y por qué ese resultado es el correcto.

EXPECTED = {
    "sale.order.type": {
        # Rama '<>'. Parte de [('move_type', '<>', 'out_invoice')], que 19 normalizaba con
        # un aviso. Tiene que quedar con '!=', el mismo operador que 20 sí acepta. Si
        # sigue con '<>', el script no reescribió y el tipo de pedido no confirma pedidos.
        ref("upgrade_prepare_demo.sot_sd_not_equal"): {
            "invoice_validate_domain": "[('move_type', '!=', 'out_invoice')]",
        },
        # Rama '=='. Parte de [('state', '==', 'draft')]. Tiene que quedar con '=': si
        # quedara '==' la validación de facturas falla con ValueError en cada confirmación.
        ref("upgrade_prepare_demo.sot_sd_double_equal"): {
            "invoice_validate_domain": "[('state', '=', 'draft')]",
        },
        # Rama de mayúsculas. Parte de [('name', 'ILIKE', 'FA')]. Tiene que quedar 'ilike'
        # y el valor 'FA' intacto: si se pasara a minúsculas el valor también, el filtro
        # cambiaría qué facturas matchea.
        ref("upgrade_prepare_demo.sot_sd_uppercase"): {
            "invoice_validate_domain": "[('name', 'ilike', 'FA')]",
        },
        # Expresión dinámica. Parte de [('invoice_date', '<>', context_today())]. El campo
        # se renderiza con allow_expressions=True, así que puede traer context_today() o
        # relativedelta(...). Se reescribe el operador y la llamada queda como está: si acá
        # aparece una fecha concreta, alguien metió un safe_eval y le congeló al cliente la
        # ventana de validación en la fecha de la migración.
        ref("upgrade_prepare_demo.sot_sd_dynamic"): {
            "invoice_validate_domain": "[('invoice_date', '!=', context_today())]",
        },
        # El otro campo, que se evalúa contra sale.order. Parte de
        # [('state', '==', 'sale')] en sale_order_filter_domain. Tiene que quedar con '=':
        # si solo se reescribiera invoice_validate_domain, este tipo seguiría rompiendo.
        ref("upgrade_prepare_demo.sot_sd_sale_order_filter"): {
            "sale_order_filter_domain": "[('state', '=', 'sale')]",
        },
        # Preservación: dominios que ya son válidos en 20. No tienen nada que reescribir y
        # tienen que quedar idénticos, uno por campo. Si cambian, el script le está
        # escribiendo a un dominio que no lo necesitaba.
        ref("upgrade_prepare_demo.sot_sd_valid"): {
            "invoice_validate_domain": "[('move_type', '=', 'out_invoice')]",
            "sale_order_filter_domain": "[('state', '=', 'sale')]",
        },
        # Preservación: campo que Odoo 20 ya no tiene (sale.order.require_payment). Parte de
        # [('require_payment', '=', True)]. No hay a dónde llevar la condición, y sacarla
        # cambiaría qué pedidos se facturan solos; el script la deja como está y la reporta.
        # Si acá apareciera otra cosa, el script estaría inventando un reemplazo.
        ref("upgrade_prepare_demo.sot_sd_missing_field"): {
            "sale_order_filter_domain": "[('require_payment', '=', True)]",
        },
        # Las dos cosas a la vez: parte de [('checked', '<>', True)] (account.move.checked
        # ya no existe en 20). Se reescribe el operador, que es mecánico, y el campo queda:
        # si el operador siguiera siendo '<>', el tipo fallaría por el operador además de
        # por el campo; y si el campo desapareciera, el script estaría decidiendo por el PO.
        ref("upgrade_prepare_demo.sot_sd_mixed"): {
            "invoice_validate_domain": "[('checked', '!=', True)]",
        },
    },
}
