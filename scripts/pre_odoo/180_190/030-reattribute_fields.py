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
    # Mismo caso por otra via: saas_client_adhoc le agrega `lines` a ir.ui.view y estos dos
    # modelos de Odoo hacen _inherits de ahi, asi que el campo delegado queda a nombre de
    # `website`. No aborta como los de arriba (lo reporta odoo.upgrade.util como CRITICAL y
    # sigue), pero Odoo borra el campo en su corrida y lo recrea despues nuestro `-u all`.
    ("website.controller.page", "lines", "saas_client_adhoc"),
    ("website.page", "lines", "saas_client_adhoc"),
    # La variante inversa: el modelo es de la OCA y los campos son de Odoo. product.customerinfo
    # (OCA product_customerinfo) nace con `_inherit = "product.supplierinfo"` + `_name` propio,
    # asi que hereda todo lo que otros modulos le agregan al padre y el ORM registra esos xmlid
    # contra el modulo que los declara, todos de Odoo. purchase_requisition_line_id es el unico
    # almacenado: ahi el script de `base` aborta. Los otros cuatro los reporta como CRITICAL y
    # sigue, pero se reatribuyen igual para que Odoo no los borre. Detectado en el request 12182.
    ("product.customerinfo", "purchase_requisition_line_id", "product_customerinfo"),
    ("product.customerinfo", "purchase_requisition_id", "product_customerinfo"),
    ("product.customerinfo", "last_purchase_date", "product_customerinfo"),
    ("product.customerinfo", "show_set_supplier_button", "product_customerinfo"),
    ("product.customerinfo", "is_subcontractor", "product_customerinfo"),
]


def migrate(cr, version):
    """Reatribuye el xmlid de los campos de FIELD_OWNERS al modulo que los declara."""
    for model, fieldname, module in FIELD_OWNERS:
        # Convencion de nombre de xmlid de campo del ORM, misma que usa odoo.upgrade.util
        xmlid_name = "field_%s__%s" % (model.replace(".", "_"), fieldname)
        # Un mismo campo puede llegar con mas de un xmlid con este name: al actualizar su modulo,
        # Odoo deja el viejo huerfano (modulo `__export__`) y crea el suyo. Moverlos todos de una
        # viola ir_model_data_module_name_uniq_index, asi que primero se elige cual queda: el que
        # apunta a un campo que existe, despues el que ya esta a nombre del modulo, despues el de
        # un modulo instalado, y a igualdad el mas viejo. Detectado en el request 12411.
        cr.execute(
            """
            SELECT d.id, d.module, d.res_id
              FROM ir_model_data d
             WHERE d.model = 'ir.model.fields'
               AND d.name = %s
             ORDER BY EXISTS (SELECT 1 FROM ir_model_fields f WHERE f.id = d.res_id) DESC,
                      (d.module = %s) DESC,
                      EXISTS (SELECT 1 FROM ir_module_module m
                               WHERE m.name = d.module AND m.state != 'uninstalled') DESC,
                      d.id
            """,
            (xmlid_name, module),
        )
        rows = cr.fetchall()
        if not rows:
            _logger.info("No xmlid for %s.%s, nothing to reattribute", model, fieldname)
            continue

        keep_id, keep_module, keep_res_id = rows[0]
        # Del mismo campo y de un modulo instalado: esos son los que reclaman el campo y los
        # unicos que chocan al mover. Una fila que apunta a otro campo no se toca, aunque comparta
        # el name; un huerfano no lo reclama nadie y se deja donde esta.
        cr.execute(
            """
            DELETE FROM ir_model_data d
             WHERE d.model = 'ir.model.fields'
               AND d.name = %s
               AND d.id != %s
               AND d.res_id = %s
               AND EXISTS (SELECT 1 FROM ir_module_module m
                            WHERE m.name = d.module AND m.state != 'uninstalled')
         RETURNING d.id, d.module
            """,
            (xmlid_name, keep_id, keep_res_id),
        )
        dropped = cr.fetchall()
        if dropped:
            # El log del pase es la unica traza: que se borro, no cuantos
            _logger.info(
                "Dropped duplicate xmlid(s) of %s.%s: %s",
                model,
                fieldname,
                ", ".join("id %s (module %s)" % (row_id, row_module) for row_id, row_module in dropped),
            )

        if keep_module == module:
            _logger.info("%s.%s already belongs to %s", model, fieldname, module)
            continue
        cr.execute("UPDATE ir_model_data SET module = %s WHERE id = %s", (module, keep_id))
        _logger.info("Reattributed %s.%s to %s (was %s)", model, fieldname, module, keep_module)
