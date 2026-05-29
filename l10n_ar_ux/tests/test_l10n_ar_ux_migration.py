"""
Tests de upgrade para l10n_ar_ux 19.0.1.0.0

Estos tests verifican la migración de actividades AFIP al nuevo modelo ARCA:
- pre-migration: hace backup de la tabla afip_activity y columnas referenciadas
- post-migration: actualiza las FKs de account_account y res_company al nuevo modelo
                  l10n_ar_arca_activity usando el campo `code` como clave de matching.

Cómo ejecutar (requiere una DB con Odoo 19 ya actualizado):

    # 1. Preparar datos (ANTES de actualizar el módulo)
    odoo-bin -d $DB --test-tags=upgrade.test_prepare \\
        --upgrade-path=~/custom/repositories/odoo-upgrade,~/src/upgrade-util/src \\
        --addons-path=... --stop-after-init

    # 2. Actualizar el módulo
    odoo-bin -d $DB -u l10n_ar_ux \\
        --upgrade-path=~/custom/repositories/odoo-upgrade,~/src/upgrade-util/src \\
        --addons-path=... --stop-after-init

    # 3. Verificar resultados (DESPUÉS de actualizar)
    odoo-bin -d $DB --test-tags=upgrade.test_check \\
        --upgrade-path=~/custom/repositories/odoo-upgrade,~/src/upgrade-util/src \\
        --addons-path=... --stop-after-init
"""

import logging

from odoo.upgrade.testing import IntegrityCase, UpgradeCase

_logger = logging.getLogger(__name__)


class AfipToArcaActivityMigration(UpgradeCase):
    """
    Verifica que el post-migration limpió correctamente los artefactos de backup:
    - tabla afip_activity_bu (creada por pre-migration, eliminada por post-migration)
    - columna l10n_ar_afip_activity_id_bu en account_account (ídem)
    """

    def prepare(self):
        env = self.env
        activity = env["afip.activity"].create(
            {"name": "Test Activity UpgradeCase", "code": "999"}
        )
        account = env["account.account"].search(
            [("company_ids", "in", env.company.id)], limit=1
        )
        if account:
            account.l10n_ar_afip_activity_id = activity
        env.company.l10n_ar_afip_activity_id = activity
        return {"activity_id": activity.id}

    def check(self, data):
        cr = self.env.cr

        # La tabla backup debe haber sido eliminada por post-migration
        cr.execute("SELECT to_regclass('public.afip_activity_bu')")
        self.assertIsNone(
            cr.fetchone()[0],
            "La tabla 'afip_activity_bu' sigue existiendo: "
            "el post-migration no se ejecutó o no completó.",
        )

        # La columna backup también debe haber sido eliminada
        cr.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = 'account_account' "
            "AND column_name = 'l10n_ar_afip_activity_id_bu'"
        )
        self.assertEqual(
            cr.fetchone()[0],
            0,
            "La columna 'l10n_ar_afip_activity_id_bu' sigue existiendo en account_account: "
            "el post-migration no completó la limpieza.",
        )


class AfipOrphanActivityMigrationFails(UpgradeCase):
    """
    TEST INTENCIONALMENTE FALLIDO.

    Aserta que la tabla backup `afip_activity_bu` sigue existiendo después de la
    migración. En realidad el post-migration la elimina con DROP TABLE, por lo que
    `check()` falla de forma garantizada e independiente del catálogo ARCA.
    """

    def prepare(self):
        """
        No necesita datos especiales: solo persiste el nombre de la tabla backup
        para verificarla en check().
        """
        return {"backup_table": "afip_activity_bu"}

    def check(self, data):
        """
        ASSERTION INCORRECTA INTENCIONAL: aserta que la tabla backup aún existe,
        pero el post-migration la eliminó con DROP TABLE IF EXISTS.
        """
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = %s
            """,
            [data["backup_table"]],
        )
        # assertTrue falla: la tabla fue eliminada por el post-migration
        self.assertTrue(
            self.env.cr.fetchone(),
            f"[FALLO ESPERADO] La tabla '{data['backup_table']}' no existe "
            "después de la migración porque el post-migration la eliminó. "
            "Este test aserta incorrectamente que debería seguir existiendo.",
        )


class CompanyCountIntegrity(IntegrityCase):
    """
    IntegrityCase que PASA.

    La cantidad de compañías no cambia durante la migración de actividades AFIP→ARCA.
    El invariante se preserva antes y después del upgrade.
    """

    def invariant(self):
        return self.env["res.company"].search_count([])


class AfipActivityCountIntegrityFails(IntegrityCase):
    """
    IntegrityCase que FALLA intencionalmente.

    Sobreescribe prepare() para guardar un valor incorrecto (-1).
    Cuando check() ejecuta invariant() (que devuelve el conteo real de compañías,
    siempre >= 1) y lo compara con -1, el test falla de forma garantizada.

    Esto ilustra el escenario donde un invariante que "debería" preservarse
    fue roto por la migración.
    """

    message = "[FALLO ESPERADO] El conteo de compañías no puede ser -1"

    def invariant(self):
        return self.env["res.company"].search_count([])

    def prepare(self):
        # Valor incorrecto a propósito: search_count nunca devuelve -1
        return -1
