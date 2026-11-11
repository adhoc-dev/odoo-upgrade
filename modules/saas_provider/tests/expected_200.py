# Test declarativo de los scripts de saas_provider en el salto a 20.
#
# 20.0.1.0.0/pre-migration.py: sale el Postgres compartido. Se borran los campos
# postgres_mode y postgres_server_id(s), el cron de bases colgadas, los modelos
# saas.postgres.server y saas.environment.postgres.server, y el parametro
# saas_postgres_server.use_tunnel. No tiene caso aca: ningun dato pasa a otro
# lado, lo que ya no esta no se puede declarar, y lo que queda es data del
# modulo que el -u vuelve a cargar. Lo cubre que el -u termine sin errores.
#
# scripts/pre_upgrade/190_200/saas_provider_untranslate_analytic_account_name.py:
# account.analytic.account.name deja de ser traducible. Antes del -u, el script
# copia es_419 a en_US donde difieren y lo marca no traducible en
# ir_model_fields, para que el -u convierta la columna conservando en_US:
#
#   es_419 distinto de en_US  ->  queda el nombre de es_419
#   sin es_419                ->  queda el nombre de en_US

EXPECTED = {
    "account.analytic.account": {
        # Rama es_419 distinto de en_US. Parte de en_US = "Account old name" y
        # es_419 = "Cuenta nombre nuevo". Si queda el nombre en ingles, el script
        # no corrio antes del -u y la cuenta volvio a su nombre viejo.
        ref("upgrade_prepare_demo.analytic_account_renamed_in_es_419"): {
            "name": "Cuenta nombre nuevo",
        },
        # Preservacion: la cuenta tiene el nombre solo en en_US. Si cambia o
        # queda vacio, el script piso una cuenta que no tenia que tocar.
        ref("upgrade_prepare_demo.analytic_account_only_en_us"): {
            "name": "Account only in English",
        },
    },
}
