import logging

_logger = logging.getLogger(__name__)

# Casos de la migracion STORE TO BRANCH de base/19.0.0.0 (pre-migration.py
# respalda res_store y los store_id; end-migration.py resuelve cada store a una
# company y reescribe los company_id de los registros que lo referenciaban).
# Los verifica base/tests/expected_190.py.
#
# POR QUE HAY QUE SEMBRAR (la base canonica NO alcanza como ancla):
# la base ya trae stores (Rosario, Buenos Aires, Unidad A/B) y registros que los
# referencian, pero ni los stores ni ninguna de las companies destino tienen
# xmlid — las branches las CREA la migracion, y un registro creado por la
# migracion no se puede referenciar (ADR 0007: el check resuelve los ref contra
# ir_model_data). La unica forma de tener una company destino referenciable es
# que exista ANTES con su xmlid: get_store_to_company_mapping resuelve cada
# store primero por company homonima ya existente y recien despues crea una
# branch nueva. Esta siembra entra por ese camino.
#
# _load_records (nativo de BaseModel) registra los xmlids estables en
# ir.model.data bajo el modulo virtual 'upgrade_prepare_demo' (mismo mecanismo
# que '__export__': ningun addon lo carga, asi que _process_end nunca los
# reapea) y es idempotente: re-correr el script no duplica registros.

NAME = "Sucursal Declarativa"
COMPANY_XMLID = "upgrade_prepare_demo.company_store_to_branch"
STORE_XMLID = "upgrade_prepare_demo.store_to_branch"


def migrate(env):
    if "res.store" not in env:
        _logger.info("multi_store no esta en esta base - no se siembra nada")
        return
    Journal = env["account.journal"]
    if "store_id" not in Journal._fields:
        _logger.info("account_multi_store no esta en esta base - no se siembra nada")
        return

    main_company = env.ref("base.main_company")

    # 1. La company destino, con xmlid. end-migration la encuentra por nombre
    #    (Company.search([("name", "=", store_name)])) y la cuelga de la parent
    #    en vez de crear una branch nueva. Se crea SIN parent_id, igual que las
    #    que crea la migracion, y sin plan de cuentas: asi es como nacen todas
    #    las branches de este script (copy_parent_account_defaults_to_branches
    #    es justamente la contraparte de eso).
    env["res.company"]._load_records([{
        "xml_id": COMPANY_XMLID,
        "values": {"name": NAME, "currency_id": main_company.currency_id.id},
        "noupdate": True,
    }])
    company = env.ref(COMPANY_XMLID)

    # 2. El store homonimo. Cuelga de un store que YA es padre de otro, a
    #    proposito: get_store_to_company_mapping toma como store raiz el primero
    #    sin parent_id y resuelve la company parent de TODA la corrida con un
    #    DISTINCT sobre los parent_id de la tabla. Un store raiz de mas, o un
    #    parent_id nuevo, moveria esas dos cosas para todos los demas casos de
    #    la base. Colgarlo de un padre que ya existe no cambia ninguno de los
    #    dos conjuntos.
    Store = env["res.store"]
    parent_store = Store.search([("parent_id", "!=", False)], limit=1).parent_id
    Store._load_records([{
        "xml_id": STORE_XMLID,
        "values": {
            "name": NAME,
            "company_id": main_company.id,
            "parent_id": parent_store.id or False,
        },
        "noupdate": True,
    }])
    store = env.ref(STORE_XMLID)

    # 3. Los dos diarios del caso. account.journal es uno de los tres modelos
    #    con store_id PROPIO (no related) — los related los saltea
    #    migrate_store_fields_to_company a proposito —, y es el que mas duele si
    #    se mueve mal. Los codes son de 5 chars y no chocan con ninguno de la
    #    base, para no meter a estos dos en _resolve_journal_code_collisions.
    Journal._load_records([{
        # Rama principal: store -> company homonima.
        "xml_id": "upgrade_prepare_demo.journal_store_to_branch",
        "values": {
            "name": "Upgrade Store To Branch",
            "code": "UPSTB",
            "type": "general",
            "company_id": main_company.id,
            "store_id": store.id,
        },
        "noupdate": True,
    }, {
        # Rama de preservacion: sin store, se queda donde esta.
        "xml_id": "upgrade_prepare_demo.journal_no_store",
        "values": {
            "name": "Upgrade No Store",
            "code": "UPNST",
            "type": "general",
            "company_id": main_company.id,
        },
        "noupdate": True,
    }])

    _logger.info(
        "Seeded the store-to-branch case: store %s (ID: %s) -> company %s (ID: %s)",
        NAME, store.id, company.name, company.id,
    )
