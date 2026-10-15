# Test declarativo de modules/base/0.0.0/end-220-account_groups_to_parent_accounts.py.
#
# La transformacion: 20 elimina account.group y sus planes traen cada grupo como
# una cuenta padre archivada, con el xmlid que tenia el grupo. El script arma lo
# mismo con lo que respaldo scripts/pre_odoo/always/220-backup_account_groups.py:
#
#   grupo                       -> cuenta archivada, con el xmlid del grupo
#   grupo hijo                  -> cuenta archivada colgada de la del grupo padre
#   cuenta comun                -> colgada de la cuenta de su grupo mas profundo,
#                                  y sigue activa (preservacion)
#
# Se declara el estado final, lo deje el pase de Odoo o este script: si el pase
# ya arma la jerarquia, el script no hace nada y el check sigue en verde.
#
# Las companias son las de la base canonica de 19: 7 Muebleria ARG (ar_ri) y
# 4 Muebleria ES (es_pymes, un plan cuyos grupos 20 ya no trae).
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007).

EXPECTED = {
    "account.account": {
        # Rama "grupo raiz": el grupo 1 Activo de ar_ri tiene que quedar como cuenta
        # archivada y sin padre. Si el ref falta, nadie convirtio los grupos; si
        # queda activa, se le pueden cargar asientos. El codigo no se declara: en 20
        # depende de la compania, y el check lee con la del usuario.
        company_ref(7, "account.account_group_activo"): {
            "active": False,
            "parent_id": None,
        },
        # Rama "grupo hijo": 1.1.1 Cajas y Bancos colgaba de 1.1 Activo Corriente.
        # Si el padre no es ese, la jerarquia se armo con otro criterio que el de
        # los grupos de 19.
        company_ref(7, "account.account_group_cajas_y_bancos"): {
            "active": False,
            "parent_id": company_ref(7, "account.account_group_activo_corriente"),
        },
        # Rama "cuenta comun": 1.1.3.01.010 Deudores por ventas estaba en el grupo
        # 1.1.3 Creditos por ventas. Tiene que colgar de esa cuenta padre y seguir
        # activa: si queda archivada, la compania no puede facturar.
        company_ref(7, "account.base_deudores_por_ventas"): {
            "active": True,
            "parent_id": company_ref(7, "account.account_group_creditos_por_ventas"),
        },
        # Rama "plan sin grupos en 20": es_pymes ya no trae grupos, asi que la cuenta
        # 572 sale solo del respaldo. Parte del grupo 572 dentro de 57.
        company_ref(4, "account.account_group_572"): {
            "active": False,
            "parent_id": company_ref(4, "account.account_group_57"),
        },
        # Cuenta comun de ese plan: 572000 Bancos estaba en el grupo 572. Si no
        # cuelga de ahi, el script ignoro los grupos de los planes que 20 no migra.
        company_ref(4, "account.account_common_572"): {
            "active": True,
            "parent_id": company_ref(4, "account.account_group_572"),
        },
    },
}
