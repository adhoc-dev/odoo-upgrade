# Test declarativo de los scripts de saas_provider/20.0.1.0.0/.
#
# pre-migration.py: sale el Postgres compartido. Se borran los campos
# postgres_mode y postgres_server_id(s), el cron de bases colgadas, los modelos
# saas.postgres.server y saas.environment.postgres.server, y el parametro
# saas_postgres_server.use_tunnel.

NO_CHECK = (
    "El script solo borra modelos, campos, un cron y un parametro, y ningun dato "
    "pasa a otro lado. Lo que ya no esta no se puede declarar (un ref ausente es "
    "FAIL siempre), y lo que queda es data del modulo que el -u vuelve a cargar, "
    "asi que un check daria verde igual. Lo cubre que el -u termine sin errores."
)
