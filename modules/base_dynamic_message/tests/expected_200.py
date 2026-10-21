# Test declarativo de base_dynamic_message/20.0.1.0.0/pre-migration.py en el salto a 20.
#
# La transformacion: 19 aceptaba con un aviso los operadores <>, == y los
# escritos en mayuscula; 20 los rechaza con "Invalid operator". El script los
# pasa a la forma de 20 en el dominio de cada linea, en su codigo y en el
# compute del campo del mensaje:
#
#   <>               -> !=
#   ==               -> =
#   ILIKE, IN, ...   -> ilike, in, ...
#   operador valido  -> no se toca (preservacion)
#
# La siembra (tests/pre_odu/base_dynamic_message/190_200/010-domain_operators.py)
# carga un mensaje sobre contactos con una linea por rama, sin confirmarlo. El
# compute del campo lo cubre modules/base_dynamic_message/tests/test_pre_migration.py.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "ir.model.dynamic_message.line": {
        # Rama '<>' -> '!='. Parte de [("email", "<>", False)]. Si sigue '<>', en
        # 20 el formulario de contactos da "Invalid operator" para todos.
        ref("upgrade_prepare_demo.dynamic_message_line_ne"): {
            "domain": '[("email", "!=", False)]',
            "code": '\nif rec in rec.filtered_domain([("email", "!=", False)]):\n'
            "    messages.append('Tiene email')\n",
        },
        # Rama '==' -> '='. Parte de [("name", "==", "Azure Interior")]. Verifica
        # tambien que el codigo cambie igual que el dominio.
        ref("upgrade_prepare_demo.dynamic_message_line_eq"): {
            "domain": '[("name", "=", "Azure Interior")]',
            "code": '\nif rec in rec.filtered_domain([("name", "=", "Azure Interior")]):\n'
            "    messages.append('Es Azure')\n",
        },
        # Rama mayuscula -> minuscula. Parte de [("name", "ILIKE", "azure")]; en
        # 19 se pasaba a minuscula al evaluar, en 20 ya no.
        ref("upgrade_prepare_demo.dynamic_message_line_upper"): {
            "domain": '[("name", "ilike", "azure")]',
            "code": '\nif rec in rec.filtered_domain([("name", "ilike", "azure")]):\n'
            "    messages.append('Parece Azure')\n",
        },
        # Preservacion: un dominio valido con el valor "IN" en una lista. Si
        # cambia, el script tomo un valor por un operador y altero el filtro.
        ref("upgrade_prepare_demo.dynamic_message_line_valid"): {
            "domain": '[("ref", "in", ["A", "IN"])]',
            "code": '\nif rec in rec.filtered_domain([("ref", "in", ["A", "IN"])]):\n'
            "    messages.append('Referencia A o IN')\n",
        },
    },
}
