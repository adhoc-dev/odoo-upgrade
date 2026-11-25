# Test declarativo de scripts/pre_upgrade/190_200/product_management_group_to_native.py.
#
# La transformacion: antes del -u, los usuarios internos de Products Management reciben
# Productos / Crear y el modulo se desinstala, con su grupo.
#
#   interno con el grupo del modulo         -> pasa a Productos / Crear
#   portal con el grupo del modulo          -> pierde el grupo y no recibe el nativo
#   interno con Productos / Crear, sin el   -> no se toca (preservacion)
#
# Los siembra tests/pre_odu/product_management_group/190_200/010-users_of_the_group.py.
# Se declaran los grupos explicitos (group_ids), no los implicados.
EXPECTED = {
    "res.users": {
        # Interno con Products Management: recibe Productos / Crear y el grupo del modulo
        # desaparece con el modulo. Si no tiene el nativo, el script no le paso el permiso y
        # el usuario deja de poder crear productos.
        ref("upgrade_prepare_demo.user_pmg_internal"): {
            "group_ids": [ref("base.group_user"), ref("product.group_product_manager")],
        },
        # Portal con Products Management: no recibe el nativo, que implica Usuario interno.
        # Si lo tiene, el script convirtio a un usuario de portal en interno.
        ref("upgrade_prepare_demo.user_pmg_portal"): {
            "group_ids": [ref("base.group_portal")],
        },
        # Preservacion: ya tenia Productos / Crear y nunca tuvo el grupo del modulo. Si
        # cambia, el script toco usuarios que no eran del grupo.
        ref("upgrade_prepare_demo.user_pmg_native_only"): {
            "group_ids": [ref("base.group_user"), ref("product.group_product_manager")],
        },
    },
}
