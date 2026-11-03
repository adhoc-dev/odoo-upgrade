# Test declarativo de los scripts de saas_provider_adhoc/20.0.1.0.0/.
#
# pre-migration.py: se borran las comunicaciones por facturas impagas, que se
# deprecan en 20: el cron, las 4 categorias unpaid_* y sus comunicaciones.
#
#   categoria General -> sigue, con su nombre (preservacion)
#
# Que el cron y las categorias unpaid_* ya no esten no se puede declarar: un
# registro ausente es FAIL siempre (tests/post_odu/README.md). Lo cubre la
# corrida del -u en runbot, que falla si el script falla.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "saas.communication.category": {
        # Preservacion: la categoria de la data del modulo que no es de impagas.
        # Si desaparece, el script borro de mas.
        ref("saas_provider_adhoc.general_category"): {
            "name": "General",
        },
    },
}
