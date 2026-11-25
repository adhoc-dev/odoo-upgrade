import logging

_logger = logging.getLogger(__name__)

# Siembra de usuarios para scripts/pre_upgrade/190_200/product_management_group_to_native.py:
# quien tiene Products Management pasa a Productos / Crear y el modulo se desinstala. Lo
# verifica modules/product_management_group/tests/expected_200.py.
#
# La demo no trae un usuario de portal en el grupo ni uno con Productos / Crear sin el
# grupo, y el admin tiene demasiados grupos para declararlos todos: cada caso es un usuario
# con los grupos justos.
MODULE_GROUP = "product_management_group.group_products_management"
NATIVE_GROUP = "product.group_product_manager"
CASES = [
    # (xmlid, login, grupos)
    ("user_pmg_internal", "pmg_internal", ["base.group_user", MODULE_GROUP]),
    ("user_pmg_portal", "pmg_portal", ["base.group_portal", MODULE_GROUP]),
    ("user_pmg_native_only", "pmg_native_only", ["base.group_user", NATIVE_GROUP]),
]


def migrate(env):
    if not env.ref(MODULE_GROUP, raise_if_not_found=False):
        return
    records = []
    for name, login, groups in CASES:
        records.append(
            {
                "xml_id": "upgrade_prepare_demo.%s" % name,
                "values": {
                    "name": login,
                    "login": login,
                    "group_ids": [(6, 0, [env.ref(g).id for g in groups])],
                },
                "noupdate": True,
            }
        )
    env["res.users"].with_context(no_reset_password=True)._load_records(records)
    _logger.info("Seeded %s users for product_management_group", len(records))
