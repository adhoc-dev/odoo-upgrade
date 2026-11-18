import logging

_logger = logging.getLogger(__name__)

# Campos de l10n_ar_stock que cambian de módulo dueño (18 -> 19): en 18 los declara
# l10n_ar_stock (Adhoc) sobre modelos de Odoo; en 19 el módulo l10n_ar_stock pasa a ser el de
# Odoo y el pase borra las columnas, que l10n_ar_stock_ux recrea vacías. Los verifica
# modules/l10n_ar_stock/tests/expected_190.py: el valor tiene que sobrevivir al pase gracias a
# scripts/pre_odoo/180_190/070-backup_l10n_ar_stock_fields.py + el restore del end-migration.
# Se siembran dispatch_number (lote y remito), cot (remito) y arba_code (producto) para
# ejercitar el camino genérico; arba_cot (compañía) ya lo siembra 040-cot_key_on_branch.py.
#
# _load_records (nativo de BaseModel) registra los xmlids en ir.model.data bajo el módulo
# virtual 'upgrade_prepare_demo' y es idempotente: re-correr el script no duplica registros.
DISPATCH_LOTE = "DESP-LOTE-18"
DISPATCH_REMITO = "DESP-REMITO-18"
COT_REMITO = "COT-REMITO-18"
ARBA_CODE = "180190"  # arba_code: 6 dígitos numéricos exactos (check_arba_code de product.template)


def migrate(env):
    if "dispatch_number" not in env["stock.lot"]._fields:
        _logger.info("Esta base no tiene los campos de l10n_ar_stock de 18 — no se siembra nada")
        return

    env["product.product"]._load_records([{
        "xml_id": "upgrade_prepare_demo.product_dispatch",
        "values": {"name": "Producto despacho (upgrade test)", "tracking": "lot", "arba_code": ARBA_CODE},
        "noupdate": True,
    }])
    product = env.ref("upgrade_prepare_demo.product_dispatch")

    env["stock.lot"]._load_records([
        # Lote con despacho: tiene que llegar a 19 con el mismo número.
        {
            "xml_id": "upgrade_prepare_demo.lot_with_dispatch",
            "values": {"name": "LOTE-DESP-1", "product_id": product.id, "dispatch_number": DISPATCH_LOTE},
            "noupdate": True,
        },
        # Control: lote sin despacho. Verifica que el restore no le invente un número a los
        # registros que no estaban en el respaldo.
        {
            "xml_id": "upgrade_prepare_demo.lot_without_dispatch",
            "values": {"name": "LOTE-DESP-2", "product_id": product.id},
            "noupdate": True,
        },
    ])

    # Remito con despacho y cot: ejercita el respaldo multi-columna de stock_picking.
    picking_type_in = env.ref("stock.picking_type_in")
    env["stock.picking"]._load_records([{
        "xml_id": "upgrade_prepare_demo.picking_with_dispatch",
        "values": {
            "picking_type_id": picking_type_in.id,
            "location_id": env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": env.ref("stock.stock_location_stock").id,
            "dispatch_number": DISPATCH_REMITO,
            "cot": COT_REMITO,
        },
        "noupdate": True,
    }])
    _logger.info("Sembrados producto, lote y remito con campos de l10n_ar_stock para los tests")
