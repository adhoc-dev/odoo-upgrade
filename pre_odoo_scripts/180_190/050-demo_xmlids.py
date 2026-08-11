import logging

_logger = logging.getLogger(__name__)

# OJO: esto es para la base demo, no para clientes. Vive aca y no en upgrade-prepare-demo solo
# porque ese repo esta tomado por otro trabajo. Hoy no molesta porque el step que corre estos
# scripts todavia no esta en produccion, pero cuando se active le va a tocar el dato a cada
# cliente que actualice. Sacarlo de aca antes de ese momento.
#
# En 19 varios xmlids del demo de `product` no salen de un <record> sino de un
# <function name="_update_xmlids">. Los archivos demo se cargan con noupdate=True y en un
# upgrade el modo es `update`, combinacion con la que convert.py:_tag_function saltea los
# <function>. Entonces el xmlid nunca se registra y el <record> que lo referencia tres lineas
# despues muere con "External ID not found in the system".
#
# Y no se cae solo ese modulo: loading.py:load_demo envuelve el demo completo del paquete en un
# savepoint, asi que al fallar product_demo.xml se revierte tambien product_attribute_demo.xml
# y se pierde product.pa_brand, que despues reclama website_sale_comparison. Un xmlid faltante
# se lleva puestos 8 modulos (build 101949).
#
# Aca creamos por adelantado los que son triviales de resolver: el template de un producto
# concreto. Los otros candidatos de la lista de 19 se resuelven con
# _get_variant_for_combination() o con el orden de un o2m, y esos no se replican en SQL.
#
# (xmlid del product.product de origen, xmlid del product.template a crear)
TEMPLATE_XMLIDS = [
    ("product_product_5", "product_template_5"),
    ("product_product_8", "product_template_8"),
]


def migrate(cr, version):
    """Crea los xmlids de product.template que en 19 registra un <function> del demo."""
    for source, target in TEMPLATE_XMLIDS:
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate, create_date, write_date)
                 SELECT 'product', %s, 'product.template', pp.product_tmpl_id, true, now(), now()
                   FROM ir_model_data d
                   JOIN product_product pp ON pp.id = d.res_id
                  WHERE d.module = 'product'
                    AND d.name = %s
                    AND d.model = 'product.product'
                    AND NOT EXISTS (
                            SELECT 1 FROM ir_model_data
                             WHERE module = 'product' AND name = %s
                        )
            """,
            (target, source, target),
        )
        _logger.info("Created xmlid product.%s from product.%s (%s row(s))", target, source, cr.rowcount)
