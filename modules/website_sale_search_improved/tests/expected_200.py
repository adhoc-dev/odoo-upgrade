# website_sale_search_improved 19 -> 20 (tarea 76558).
#
# Los campos de busqueda extra (website_sale_search_improved.search_fields) pierden los que no
# existen en el product.template de 20 y los que 20 ya busca solo. Los de descripcion quedan:
# 20 los busca solo cuando el sitio busca en descripciones. Migra
# website_sale_search_improved/20.0.1.0.0/end-migration.py.
#
# La lista la siembra tests/pre_odu/website_sale_search_improved/190_200/010-search_fields_cases.py:
#
#   x_upgrade_missing_field            -> sale
#   description_ecommerce              -> queda
#   attribute_line_ids.value_ids.name  -> sale
#   product_tag_ids.x_upgrade_missing  -> sale
#   website_meta_keywords              -> queda
EXPECTED = {
    "ir.config_parameter": {
        # Todas las ramas en una lista, porque el parametro es uno solo por base. Parte de la
        # lista sembrada de arriba. Si queda un campo que no existe, toda busqueda de la tienda
        # falla con "Invalid field"; si sale description_ecommerce, las bases que no buscan en
        # descripciones dejan de encontrar por ese campo. El orden de los que quedan se conserva.
        ref("upgrade_prepare_demo.icp_website_sale_search_fields"): {
            "value": "['description_ecommerce', 'website_meta_keywords']",
        },
    },
}
