from odoo.upgrade.testing import IntegrityCase


class TestActiveInternalUsers(IntegrityCase):
    """An upgrade must not activate or archive internal users."""

    message = "La cantidad de usuarios internos activos cambió en la actualización"

    def invariant(self):
        self.env.cr.execute("SELECT count(*) FROM res_users WHERE active AND NOT share")
        return self.env.cr.fetchone()[0]
