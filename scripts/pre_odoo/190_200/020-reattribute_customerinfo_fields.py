import logging

from oba import log_message, should_run_pre_odoo

_logger = logging.getLogger(__name__)

# Misma situacion que scripts/pre_odoo/180_190/030-reattribute_fields.py, que sigue valiendo en 20.0:
# product.customerinfo (OCA product_customerinfo) nace con `_inherit = "product.supplierinfo"` + `_name`
# propio, asi que hereda todo lo que otros modulos le agregan al padre, y el ORM registra esos xmlid
# contra el modulo que declara el campo (odoo/odoo#49354), todos de Odoo. Del lado de Odoo ese modulo
# no existe: purchase_requisition_line_id es el unico almacenado y ahi el script de `base` aborta; los
# otros cuatro los reporta como CRITICAL y sigue, pero los borra. Verificado en una base 20.0 con los
# cuatro modulos instalados: los cinco xmlid quedan a nombre de mrp_subcontracting,
# purchase_requisition y purchase_stock.
#
# (modelo, campo, modulo que lo declara)
FIELD_OWNERS = [
    ("product.customerinfo", "purchase_requisition_line_id", "product_customerinfo"),
    ("product.customerinfo", "purchase_requisition_id", "product_customerinfo"),
    ("product.customerinfo", "last_purchase_date", "product_customerinfo"),
    ("product.customerinfo", "show_set_supplier_button", "product_customerinfo"),
    ("product.customerinfo", "is_subcontractor", "product_customerinfo"),
]

# Corre solo en el salto a 20 (esta carpeta ya es de ese salto) y con el modulo instalado.
TARGET_VERSION = 20
MODULES = ["product_customerinfo"]


def migrate(cr, version):
    """Reatribuye el xmlid de los campos de FIELD_OWNERS al modulo que los declara.

    Modifica la base vieja, y no puede ir despues del pase: es Odoo, durante el pase, el que aborta
    o borra los campos al verlos a nombre de un modulo suyo. Queda permanente en la old.

    Sin `odoo.upgrade.util` ni `odoo.tools.SQL` a proposito: esto corre sobre la base vieja,
    con el Odoo de la version de origen.
    """
    if not should_run_pre_odoo(cr, first_target=TARGET_VERSION, last_target=TARGET_VERSION, modules=MODULES):
        return

    reattributed = []
    for model, fieldname, module in FIELD_OWNERS:
        # Convencion de nombre de xmlid de campo del ORM, misma que usa odoo.upgrade.util
        xmlid_name = "field_%s__%s" % (model.replace(".", "_"), fieldname)
        # Un mismo campo puede llegar con mas de un xmlid con este name: al actualizar su modulo,
        # Odoo deja el viejo huerfano (modulo `__export__`) y crea el suyo. Moverlos todos de una
        # viola ir_model_data_module_name_uniq_index, asi que primero se elige cual queda: el que
        # apunta a un campo que existe, despues el que ya esta a nombre del modulo, despues el de
        # un modulo instalado, y a igualdad el mas viejo.
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
        reattributed.append("%s.%s (%s)" % (model, fieldname, keep_module))

    if reattributed:
        log_message(
            cr,
            "Se reatribuyo el xmlid de campos de product.customerinfo al modulo product_customerinfo, "
            "para que Odoo no los de por propios en el pase: %s." % ", ".join(reattributed),
            "info",
        )
