# Test declarativo de los scripts de account_cashbox/20.0.1.0.0/.
#
# pre-migration.py: las cajas sin "Restringir usuarios" quedan sin usuarios
# permitidos, como las deja la 20 al desmarcar el tilde.
#
#   caja sin restriccion con usuarios -> sin usuarios
#   caja restringida con usuarios     -> mismos usuarios (preservacion)
#
# Los usuarios de la caja sin restriccion los siembra tests/pre_odu/
# account_cashbox/190_200/010-unrestricted_cashbox_with_users.py: la demo del
# modulo la trae vacia.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "account.cashbox": {
        # Rama con usuarios -> sin usuarios. Si siguen, el script no corrio:
        # la caja los muestra y, si alguien marca el tilde, quedan habilitados
        # sin que nadie los haya elegido.
        ref("account_cashbox.pop_config_not_restrict"): {
            "restrict_users": False,
            "allowed_res_users_ids": [],
        },
        # Preservacion: una caja restringida de la demo. Si pierde usuarios, el
        # script borro lo que tenia que dejar.
        ref("account_cashbox.pop_config_caja_1"): {
            "restrict_users": True,
            "allowed_res_users_ids": [
                ref("base.user_admin"),
                ref("account_cashbox.user_demo_invoicing"),
            ],
        },
    },
}
