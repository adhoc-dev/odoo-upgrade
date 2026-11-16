# Test declarativo de la migración 19->20 de account_interests.
#
# res.company.interest guarda en `domain` (Char) un dominio que se suma a la búsqueda de
# account.move.line, y el cron de intereses lo evalúa con safe_eval. Odoo 20 rechaza con
# ValueError lo que 19 aceptaba con un aviso de deprecación; el cron lo atrapa y esa
# compañía no factura intereses en el período:
#
#   '<>'  -> '!='
#   '=='  -> '='
#   operador en mayúsculas ('IN') -> en minúsculas
#
# El script de 20.0.0.0/post-migration.py reescribe el operador en el texto, sin evaluar
# el dominio ni tocar el resto. Un campo que 20 ya no tiene (move_id.checked) no tiene
# equivalente: el script no lo toca y lo reporta a la nota del cliente.
#
# Solo se declara el estado esperado DESPUÉS del -u (ADR 0007): la base que recibimos se
# da por buena. Los registros llegan por xmlid desde la siembra de este mismo repo
# (tests/pre_odu/account_interests/190_200/010-saved_domain_cases.py).

EXPECTED = {
    "res.company.interest": {
        # Rama '<>'. Parte de [('move_id.move_type', '<>', 'out_refund')], el caso del
        # ticket. Tiene que quedar con '!='. Si sigue con '<>', el script no reescribió y
        # el cron saltea la compañía.
        ref("upgrade_prepare_demo.rci_sd_not_equal"): {
            "domain": "[('move_id.move_type', '!=', 'out_refund')]",
        },
        # Rama '=='. Parte de [('parent_state', '==', 'posted')]. Tiene que quedar con '=':
        # si quedara '==' el cron falla con ValueError en cada corrida.
        ref("upgrade_prepare_demo.rci_sd_double_equal"): {
            "domain": "[('parent_state', '=', 'posted')]",
        },
        # Rama de mayúsculas. Parte de [('move_id.name', 'NOT ILIKE', 'ND')]. Tiene que
        # quedar 'not ilike' con el valor 'ND' intacto: si se pasara a minúsculas el valor
        # también, cambiaría qué deudas generan intereses.
        ref("upgrade_prepare_demo.rci_sd_uppercase"): {
            "domain": "[('move_id.name', 'not ilike', 'ND')]",
        },
        # Expresión dinámica. Parte de [('date', '<>', context_today())]; el
        # _get_eval_context del módulo la habilita. Se reescribe el operador y la llamada
        # queda: si acá aparece una fecha concreta, alguien evaluó el dominio y lo congeló
        # en la fecha de la migración.
        ref("upgrade_prepare_demo.rci_sd_dynamic"): {
            "domain": "[('date', '!=', context_today())]",
        },
        # Preservación: dominio que ya es válido en 20. Tiene que quedar idéntico; si
        # cambia, el script le escribe a un dominio que no lo necesitaba.
        ref("upgrade_prepare_demo.rci_sd_valid"): {
            "domain": "[('move_id.move_type', '!=', 'out_refund')]",
        },
        # Las dos cosas a la vez: parte de [('move_id.checked', '<>', True)]
        # (account.move.checked ya no existe en 20). Se reescribe el operador, que es
        # mecánico, y el campo queda: si desapareciera, el script estaría decidiendo qué
        # deudas generan intereses en lugar del cliente.
        ref("upgrade_prepare_demo.rci_sd_mixed"): {
            "domain": "[('move_id.checked', '!=', True)]",
        },
    },
}
