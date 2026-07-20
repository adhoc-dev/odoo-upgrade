"""
Tests de upgrade para purchase_stock_ux 19.0

El campo `force_delivered_status` de purchase.order es un Selection stored que
cambia sus valores posibles en la 19:

    18.0: ('no', 'received')
    19.0: ('pending', 'partial', 'full')

El script de migración (todavía no escrito — los tests van primero) debe remapear
la columna persistida:

    'no'       -> vacío (NULL)
    'received' -> 'full'
    NULL / otro -> sin cambios (preservación)

Nota: el mapeo 'to receive' -> 'pending' NO aplica a este campo. 'to receive' es
un valor del campo hermano `delivery_status` (computado, eliminado en la 19), y
nunca fue un valor válido de `force_delivered_status` en 16/17/18. Esa rama es
código muerto para este campo, por eso no se testea.

Flujo de ejecución:
    1. prepare (Odoo 18):
       odoo --workers 0 --stop-after-init \\
            --test-tags=upgrade.test_prepare \\
            -d <DB> \\
            --upgrade-path=/home/odoo/custom/repositories/odoo-upgrade \\
            --without-demo=True --no-http

    2. upgrade:
       odoo --workers 0 --stop-after-init \\
            -u purchase_stock_ux \\
            -d <DB> \\
            --upgrade-path=/home/odoo/custom/repositories/odoo-upgrade \\
            --without-demo=True --no-http

    3. check (Odoo 19):
       odoo --workers 0 --stop-after-init \\
            --test-tags=upgrade.test_check \\
            -d <DB> \\
            --upgrade-path=/home/odoo/custom/repositories/odoo-upgrade \\
            --without-demo=True --no-http
"""

import logging

from odoo.upgrade.testing import IntegrityCase, UpgradeCase, change_version

_logger = logging.getLogger(__name__)


@change_version("19.0")
class PurchaseOrderForceDeliveredStatusRemap(UpgradeCase):
    """
    Verifica que la migración a 19.0 remapea los valores stored de
    `force_delivered_status` en purchase.order, cubriendo TODAS las ramas
    alcanzables con datos v18:

        'no'        -> vacío (False)
        'received'  -> 'full'
        NULL / otro -> sin cambios (preservación)

    El campo es un Selection sin compute (store por defecto): el valor queda
    persistido en la columna, por eso se aserta el valor exacto.
    """

    def prepare(self):
        partner = self.env["res.partner"].search([], limit=1)

        # Rama 'no' -> vacío. force_delivered_status='no' debe quedar sin valor.
        rec_no = self.env["purchase.order"].create({
            "name": "Test Upgrade force_delivered_status no",
            "partner_id": partner.id,
            "force_delivered_status": "no",
        })
        # Rama 'received' -> 'full'.
        rec_received = self.env["purchase.order"].create({
            "name": "Test Upgrade force_delivered_status received",
            "partner_id": partner.id,
            "force_delivered_status": "received",
        })
        # Rama de preservación: valor alcanzable fuera del mapeo (NULL, el campo
        # no tiene default). Debe quedar sin cambios tras la migración.
        rec_empty = self.env["purchase.order"].create({
            "name": "Test Upgrade force_delivered_status empty",
            "partner_id": partner.id,
        })

        return {
            "asserts": [
                {"branch": "no -> vacío", "record_id": rec_no.id, "expected": False},
                {"branch": "received -> full", "record_id": rec_received.id, "expected": "full"},
                {"branch": "preservación (NULL sin cambios)", "record_id": rec_empty.id, "expected": False},
            ],
        }

    def check(self, data):
        # Una rama sin candidato en la base falla con nombre. Sin esto, un prepare que no
        # encontro registros para una rama la dejaria sin asertar y el test daria verde.
        self.assertFalse(
            data.get("missing_branches"),
            "Ramas sin ningun registro candidato en la base: %s. El caso no se verifico."
            % (data.get("missing_branches"),),
        )
        for a in data["asserts"]:
            record = self.env["purchase.order"].browse(a["record_id"])
            with self.subTest(branch=a["branch"]):
                self.assertEqual(
                    record.force_delivered_status,
                    a["expected"],
                    "Rama '%s': force_delivered_status no quedó con el valor esperado. "
                    "Esperado %r, obtenido %r" % (
                        a["branch"], a["expected"], record.force_delivered_status,
                    ),
                )


@change_version("19.0")
class PurchaseOrderCountPreserved(IntegrityCase):
    """
    La cantidad de registros de purchase.order no debe cambiar durante la
    migración a 19.0.
    """

    def invariant(self):
        return self.env["purchase.order"].search_count([])
