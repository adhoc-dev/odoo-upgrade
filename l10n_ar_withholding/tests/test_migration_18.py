# l10n_ar_withholding/tests/test_migration_18.py
from odoo.upgrade.testing import IntegrityCase, UpgradeCase, change_version


@change_version("18.0")
class RenameCodigoRegimen(UpgradeCase):
    """El valor de codigo_regimen se preserva en l10n_ar_code tras el rename."""

    def prepare(self):
        # Usamos SQL porque en la base vieja la columna aún se llama codigo_regimen
        self.env.cr.execute(
            "UPDATE account_tax SET codigo_regimen = 'REG-TEST-001' "
            "WHERE id = (SELECT id FROM account_tax LIMIT 1) RETURNING id"
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row, "No hay taxes en la base; no se puede correr este test"
        )
        return {"tax_id": row[0], "code": "REG-TEST-001"}

    def check(self, value):
        self.env.cr.execute(
            "SELECT l10n_ar_code FROM account_tax WHERE id = %s",
            [value["tax_id"]],
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            value["code"],
            "El valor de codigo_regimen no fue preservado correctamente en l10n_ar_code",
        )


@change_version("18.0")
class AccountTaxCountIntegrity(IntegrityCase):
    """La cantidad de impuestos no cambia durante el rename de codigo_regimen."""

    message = "Taxes perdidos durante el rename de codigo_regimen a l10n_ar_code"

    def invariant(self):
        self.skip_if_demo()
        return self.env["account.tax"].search_count([])
