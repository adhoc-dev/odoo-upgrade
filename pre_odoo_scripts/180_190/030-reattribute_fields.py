import logging

_logger = logging.getLogger(__name__)

# Campos que declara un modulo nuestro sobre un modelo de Odoo y cuyo xmlid quedo a nombre de
# un modulo de Odoo. Pasa por herencia prototipo: el modulo extiende el padre (`sale.report`),
# donde la atribucion sale bien, pero en el modelo hijo el ORM registra el xmlid contra el
# modulo que define el hijo (odoo/odoo#49354). Del lado de Odoo el modulo que lo declara no
# existe, asi que al actualizar el suyo dan el campo por propio, no lo encuentran en su
# registry y lo borran: el script de `base` aborta con "you forgot to call
# `util.remove_field`". Corre dentro de la corrida de Odoo, asi que hay que reatribuirlo
# antes del dump. Mismo criterio que la upgrade line 526.
#
# (modelo, campo, modulo que lo declara)
FIELD_OWNERS = [
    # sale.subscription.report (enterprise sale_subscription) hereda de sale.report. De los 51
    # campos de sale.report, estos tres son los unicos que no declara un modulo de Odoo.
    ("sale.subscription.report", "type_id", "sale_order_type"),
    ("sale.subscription.report", "product_brand_id", "product_brand"),
    # En 19 sale_order_lot_selection ya no extiende sale.report, asi que el campo no existe mas.
    # Reatribuirlo igual alcanza: Odoo no conoce el modulo y lo deja, y el registro obsoleto lo
    # limpia nuestro `-u all` al actualizar el modulo.
    ("sale.subscription.report", "lot_id", "sale_order_lot_selection"),
]


def migrate(cr, version):
    """Reatribuye el xmlid de los campos de FIELD_OWNERS al modulo que los declara."""
    for model, fieldname, module in FIELD_OWNERS:
        # Convencion de nombre de xmlid de campo del ORM, misma que usa odoo.upgrade.util
        xmlid_name = "field_%s__%s" % (model.replace(".", "_"), fieldname)
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = %s
             WHERE model = 'ir.model.fields'
               AND name = %s
               AND module != %s
            """,
            (module, xmlid_name, module),
        )
        _logger.info(
            "Reattributed %s.%s to %s (%s row(s))", model, fieldname, module, cr.rowcount
        )
