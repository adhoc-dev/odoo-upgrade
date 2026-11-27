from odoo.upgrade.testing import IntegrityCase
from odoo.tools.safe_eval import safe_eval


class TestActiveCompanies(IntegrityCase):
    """An upgrade must not activate or archive companies."""

    message = "La cantidad de compañías activas cambió en la actualización"

    def invariant(self):
        # Read by SQL: the ir.config_parameter API changes from 20 on.
        self.env.cr.execute(
            "SELECT value FROM ir_config_parameter WHERE key = 'migration_19_end_store_to_branch'"
        )
        row = self.env.cr.fetchone()
        # The 18 -> 19 store to branch merge turns some companies into branches on purpose.
        bypass = (safe_eval(row[0]) or {}).get("b", []) if row and row[0] else []
        self.env.cr.execute(
            "SELECT count(*) FROM res_company WHERE active AND NOT (id = ANY(%s))",
            [bypass],
        )
        return self.env.cr.fetchone()[0]
