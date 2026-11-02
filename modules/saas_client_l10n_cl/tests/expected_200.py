# Test declarativo de saas_client_l10n_cl/20.0.1.0.0/end-migration.py.
#
# En 20 el modulo depende de l10n_cl_edi_fix_send_dte (bmya), que trae dos crons.
#
#   cron de envio al SII de 19 cambiado por el cliente -> mismo intervalo en el cron de bmya
#   cron de mails de aceptados con reparos             -> apagado
#
# El cambio del cron de 19 lo siembra tests/pre_odu/saas_client_l10n_cl/190_200/
# 010-send_dte_cron_changed.py, y lo respalda scripts/pre_odoo/190_200/
# 020-l10n_cl_edi_send_dte_cron.py antes del pase. La rama del cron sin cambios (queda
# en el default de bmya, cada una hora) no entra en la misma base: la cubre el
# test de pre_odoo, que no lo respalda.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007).

EXPECTED = {
    "ir.cron": {
        # Rama cambiado -> copiado: en 19 la siembra lo deja cada 4 horas. Si viene cada
        # 1 hora, el pre_odoo no lo respaldo o el end-migration no lo aplico, y el
        # cliente pierde la frecuencia que habia elegido.
        ref("l10n_cl_edi_fix_send_dte.ir_cron_send_dte_to_sii"): {
            "active": True,
            "interval_number": 4,
            "interval_type": "hours",
        },
        # Nace prendido al instalarse bmya en el -u. Si queda prendido, el
        # end-migration no lo apago y la base empieza a mandarle mails a los clientes
        # con los DTE aceptados con reparos, algo que no es de nuestro producto.
        ref("l10n_cl_edi_fix_send_dte.ir_cron_send_dte_to_partner"): {
            "active": False,
        },
    },
}
