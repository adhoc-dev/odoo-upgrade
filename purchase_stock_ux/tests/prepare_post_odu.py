"""Declaracion post-ODU para `test_purchase_stock_ux_migration`.

La corre `testing_post_odu/prepare_post_odu.py` como `--pre-upgrade-script`, sobre la base
ya devuelta por ODU y antes del `-u`. En esa ventana `purchase_order.force_delivered_status`
todavia tiene los valores de la version vieja: ODU no conoce `purchase_stock_ux`, y el
remapeo lo hace nuestro migration script durante el `-u`.

En vez de crear registros (imposible aca: las FKs y los modelos del core ya estan en la
version nueva), **referencia los que ya existen** en la demo data y anota el valor que
tienen que tener despues del pase. El `check()` del test no cambia ni distingue quien
escribio la fila de `upgrade_test_data`.

Una rama sin candidato en la base queda listada en `missing_branches` y logueada; el
`check()` la hace fallar con nombre en vez de dar falso verde. Conseguir el candidato es
el carril excepcional pre-ODU: se siembra en la preparacion de la base demo (Fase A),
viaja por ODU y a partir de ahi ya es un candidato organico mas.
"""

import logging

_logger = logging.getLogger(__name__)

# Las clases de test que se siembran, tal como las ve el framework:
# `<archivo_de_test>.<ClaseDeTest>`. El runner les antepone `purchase_stock_ux.tests.`.
REMAP_CASE = "test_purchase_stock_ux_migration.PurchaseOrderForceDeliveredStatusRemap"
COUNT_CASE = "test_purchase_stock_ux_migration.PurchaseOrderCountPreserved"

# `PurchaseOrderCountPreserved` es un IntegrityCase: su valor no es el retorno de un
# `prepare()` sino el del `invariant()` corrido sobre la base vieja. Sembrado desde aca el
# invariante queda mas angosto de lo que dice el test: compara la cantidad de purchase_order
# **despues de ODU** contra la de despues del `-u`, o sea verifica que no la cambien nuestros
# migration scripts, no que no la haya cambiado el pase de Odoo. Es lo unico verificable sin
# haber visto la base vieja, y sigue siendo mas que el skip silencioso.
INTEGRITY_CASES = {COUNT_CASE}

# (rama, condicion sobre el valor v18, valor esperado en v19). Son las mismas tres ramas
# que documenta el test; las condiciones son mutuamente excluyentes, asi que ningun
# registro puede quedar elegido para dos ramas.
BRANCHES = (
    ("no -> vacio", "force_delivered_status = 'no'", False),
    ("received -> full", "force_delivered_status = 'received'", "full"),
    ("preservacion (NULL sin cambios)", "force_delivered_status IS NULL", False),
)


def prepare(cr):
    cr.execute("SELECT to_regclass('public.purchase_order')")
    if not cr.fetchone()[0]:
        _logger.info("prepare_post_odu: purchase_order no existe, no hay nada que sembrar")
        return {}

    asserts = []
    missing_branches = []
    for branch, condition, expected in BRANCHES:
        # El ORDER BY hace determinista cual registro se elige, para que dos corridas sobre
        # el mismo zip canonico siembren lo mismo.
        cr.execute(f"SELECT id FROM purchase_order WHERE {condition} ORDER BY id LIMIT 1")
        row = cr.fetchone()
        if not row:
            missing_branches.append(branch)
            continue
        asserts.append({"branch": branch, "record_id": row[0], "expected": expected})

    if missing_branches:
        _logger.warning(
            "prepare_post_odu: sin candidato en la demo data para %s; el check las va a "
            "hacer fallar con nombre",
            ", ".join(missing_branches),
        )

    cr.execute("SELECT count(*) FROM purchase_order")
    (purchase_order_count,) = cr.fetchone()

    return {
        REMAP_CASE: {"asserts": asserts, "missing_branches": missing_branches},
        COUNT_CASE: purchase_order_count,
    }
