# Test declarativo de account_statement_base_ux/20.0.0.0/post-migration.py en el salto a 20.
#
# La transformacion: la tolerancia de pago del modulo (un importe) pasa a la nativa de 20,
# que se lee como porcentaje salvo que payment_tolerance_type diga otra cosa y que solo
# aplican las reglas de coincidencia, siempre automaticas.
#
#   automatico con tolerancia   -> regla de coincidencia, tolerancia en importe, mismo valor
#   manual con tolerancia       -> modelo de conciliacion sin tolerancia (queda en el log)
#   automatico sin tolerancia   -> no se toca (preservacion)
#
# La siembra (tests/pre_odu/account_statement_base_ux/190_200/010-payment_tolerance_cases.py)
# crea un modelo de cada tipo en 19.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que recibimos se da
# por buena.

EXPECTED = {
    "account.reconcile.model": {
        # Rama automatico con tolerancia: parte con trigger = 'auto_reconcile' y tolerancia
        # 50 (un importe). Si quedara como reco_model, la tolerancia dejaria de aplicarse; si
        # quedara en 'percentage', el 50 se leeria como 50%.
        ref("upgrade_prepare_demo.reconcile_model_tolerance_auto"): {
            "rule_type": "matching_rule",
            "payment_tolerance_type": "amount",
            "payment_tolerance": 50.0,
            "trigger": "auto_reconcile",
        },
        # Rama manual con tolerancia: parte con trigger = 'manual' y tolerancia 30. Una regla
        # de coincidencia tiene que ser automatica, asi que el script la deja sin tolerancia;
        # si conservara el 30, se leeria como 30% en un modelo que no la aplica.
        ref("upgrade_prepare_demo.reconcile_model_tolerance_manual"): {
            "rule_type": "reco_model",
            "payment_tolerance": 0.0,
            "trigger": "manual",
        },
        # Preservacion: automatico sin tolerancia (0). No es una regla de coincidencia y el
        # script no lo toca; si cambiara de tipo, el script convertiria modelos que no tenian
        # nada que migrar.
        ref("upgrade_prepare_demo.reconcile_model_no_tolerance_auto"): {
            "rule_type": "reco_model",
            "payment_tolerance": 0.0,
            "trigger": "auto_reconcile",
        },
    },
}
