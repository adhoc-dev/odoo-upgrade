from odoo.upgrade.testing import IntegrityCase, UpgradeCase, change_version


@change_version("19.0")
class EdiDocumentM2MToMany2one(UpgradeCase):
    """
    El último documento EDI de cada picking se preserva en l10n_uy_edi_reference
    tras la migración de la relación M2M a campo Many2one.

    El script pre-migration hace backup de la tabla de relación
    l10n_uy_edi_document_stock_picking_rel como _bu. El script post-migration
    migra esa relación al nuevo campo l10n_uy_edi_reference en stock_picking,
    tomando el documento con mayor id por picking (ORDER BY id DESC LIMIT 1).
    """

    def prepare(self):
        # Buscar un picking existente en la base
        self.env.cr.execute("SELECT id FROM stock_picking LIMIT 1")
        row = self.env.cr.fetchone()
        if not row:
            return None
        picking_id = row[0]

        # Buscar un documento EDI existente en la base
        self.env.cr.execute("SELECT id FROM l10n_uy_edi_document LIMIT 1")
        row = self.env.cr.fetchone()
        if not row:
            return None
        doc_id = row[0]

        # Insertar la relación en la tabla M2M original (pre-upgrade).
        # ON CONFLICT DO NOTHING por si la relación ya existía en la base.
        self.env.cr.execute(
            """
            INSERT INTO l10n_uy_edi_document_stock_picking_rel
                (stock_picking_id, l10n_uy_edi_document_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            [picking_id, doc_id],
        )
        return {"picking_id": picking_id, "doc_id": doc_id}

    def check(self, value):
        if value is None:
            return  # no había pickings o documentos EDI en la base; test no aplica
        self.env.cr.execute(
            "SELECT l10n_uy_edi_reference FROM stock_picking WHERE id = %s",
            [value["picking_id"]],
        )
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "El picking no existe después de la migración",
        )
        self.assertEqual(
            result[0],
            value["doc_id"],
            "l10n_uy_edi_reference no fue migrado correctamente desde la tabla M2M",
        )


@change_version("19.0")
class StockPickingCountIntegrity(IntegrityCase):
    """Ningún picking se pierde durante la migración de la relación EDI."""

    message = (
        "Pickings perdidos durante la migración de M2M a Many2one en l10n_uy_edi_stock"
    )

    def invariant(self):
        self.skip_if_demo()
        return self.env["stock.picking"].search_count([])
