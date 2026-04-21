import logging

from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# ============================================================================
# MIGRATION SCRIPT FOR ODOO 19 - MULTI-COMPANY/BRANCH CONSOLIDATION
# ============================================================================
#
# Este script soporta DOS modos de migración:
#
# MODO 1: STORE TO BRANCH
# -------------------------
# De: Sistema con 1 compañía y múltiples stores (res.store - ingadhoc-multi-store)
# A:  Sistema con múltiples companies en jerarquía (branches estilo Odoo 19)
#
# Características:
# - Identifica la company parent (A) = la que NO tiene parent_id
# - Cada res.store se convierte en una res.company branch
# - Los campos store_id se migran a company_id
# - Los apuntes contables se mantienen en su branch correspondiente
# - Las cuentas contables se dejan en la company parent
# - Los impuestos y configuración fiscal se fusionan/mueven a la parent
#
# MODO 2: COMPANY MERGE
# ----------------------
# De: Sistema con 2 compañías hermanas (A y B)
# A:  Sistema con jerarquía donde B es branch de A
#
# Características:
# - B se convierte en branch (hijo) de A
# - Los datos operativos se mueven a A o se mantienen en B según estrategia
# - Los datos financieros (facturas, pagos) se mantienen en B (KEEP_AND_CHECK)
# - Los maestros (partners, productos) se mantienen compartidos (KEEP)
# - La configuración contable se fusiona con la de A (MERGE_OR_MOVE)
#
# MODO 3: AUTO (DEFAULT)
# -----------------------
# Detecta automáticamente qué tipo de migración ejecutar:
# - Si existe res.store con datos -> STORE TO BRANCH
# - Si existe mapping de companies A/B -> COMPANY MERGE
# - Si no detecta nada -> No hace nada
#
# ============================================================================
# CONFIGURACIÓN
# ============================================================================
#
# Para forzar un modo específico, crear parámetro de sistema:
#   migration_19_end_mode = "store_to_branch" | "company_merge" | "auto"
#
# Para configurar el mapping manual (company_merge):
#   migration_19_end_multicompany = "{'a': 1, 'b': 2}"
#
# Para configurar el mapping manual (store_to_branch):
#   migration_19_end_store_to_branch = "{store_id: company_id, ...}"
#
# ============================================================================

# MIGRATION MODES:
# - 'company_merge': Migrates from 2 companies (A and B) to branches (B becomes child of A)
# - 'store_to_branch': Migrates from single company with multi-store to multi-company branches

# OBTENER DATA DE FIELDS EN RUNBOT, ACCION DE SERVIDOR CON
# field_targets = env['ir.model.fields'].search([
#     ('relation', '=', 'res.company'),
#     ('store', '=', True),
#     ('ttype', 'in', ['many2one', 'many2many']),
#     ('model_id.transient', '=', False),
#     ('model_id.abstract', '=', False)
# ])
# field_targets = field_targets.filtered(lambda x: env[x.model]._auto)

# res = []
# for x in field_targets:
#     res.append((x.name, x.model_id.model, x.ttype))

# company_dependent_fields = env['ir.model.fields'].search([("company_dependent", "=", True)])
# res2 = []
# for x in company_dependent_fields:
#     res2.append((x.name, x.model_id.model, x.ttype))

# raise UserError('Listado de campos de compañías: %s\n\nListado de campos company dependant: %s' % (res, res2))

# POR AHORA NO LO VEMOS NECESARIO
# Modelos que requieren renombrado para evitar errores de Constraint UNIQUE
MODELS_WITH_UNIQUE_NAMES = [
    # 'sale.order', 'purchase.order', 'stock.picking',
    # 'account.move', 'stock.warehouse', 'stock.location'
]


UNIQUE_MOVE_PREPROCESSORS = {
    "stock.location": (
        """
                        UPDATE stock_location AS loc_b
                             SET barcode = CONCAT(loc_b.barcode, '-B-', loc_b.id)
                         WHERE loc_b.company_id = %s
                             AND loc_b.barcode IS NOT NULL
                             AND EXISTS (
                                        SELECT 1
                                            FROM stock_location AS loc_a
                                         WHERE loc_a.company_id = %s
                                             AND loc_a.barcode = loc_b.barcode
                             )
                """,
    ),
    "stock.warehouse": (
        """
                        UPDATE stock_warehouse AS wh_b
                             SET name = CONCAT(wh_b.name, '-B-', wh_b.id),
                                 code = SUBSTRING(CONCAT('B', wh_b.id::text), 1, 5)
                         WHERE wh_b.company_id = %s
                             AND (EXISTS (
                                        SELECT 1
                                            FROM stock_warehouse AS wh_a
                                         WHERE wh_a.company_id = %s
                                             AND wh_a.name = wh_b.name
                             ) OR EXISTS (
                                        SELECT 1
                                            FROM stock_warehouse AS wh_a
                                         WHERE wh_a.company_id = %s
                                             AND wh_a.code = wh_b.code
                             ))
                """,
    ),
}


# Definimos criterios de equivalencia para el Merge
MERGE_CRITERIA = {
    "account.tax": ["name", "amount", "type_tax_use"],
    "account.tax.group": ["name"],
    "account.fiscal.position": ["name"],
    "account.payment.term": ["name"],
    "account.analytic.account": ["name"],
    "account.group": ["code_prefix_start"],
}

############
# STRATEGIES
############
# A. Acción MOVE_TO_PARENT (Operativo)
# Qué hace: UPDATE table SET company_id = [ID_A] WHERE company_id = [ID_B]
# Modelos: Ventas, Compras, Stock, Proyectos, Fabricación.
# Check crítico: Antes del update, verificar colisiones de nombres (ej. si el SO-001 existe en ambas empresas, renombrar el de B a "B-SO-001").

# B. Acción KEEP_AND_CHECK (Financiero)
# Qué hace: No hace nada con el company_id, pero asegura que el parent_id de la compañía B sea A.
# Modelos: Facturas (account.move), Apuntes (account.move.line), Pagos, Diarios.

# C. Acción KEEP (Maestros)
# Qué hace: No hace nada con el company_id y no chequea. Ya debería haber estado bien porque lo venían usando
# Modelos: Partners (res.partner), Productos (product.template y product.product), etc.

# D. Acción MERGE_OR_MOVE (Impuestos y Posiciones Fiscales)
# Esta es la más compleja. Si ya existe un registro equivalente en A, se combinan los registros usando "merge"
# Si no existe, se mueva a A
# TODO validar si el "move" deberíamos dejarlo archivado en "a" (Creo que si)

# POR AHORA NO UTILIZAMOS HASTA QUE NO SEA NECESARIO (ya debería haber estado bien compartido anteriormente cuando heran hermanas)
# E. Acción SET_GLOBAL (Maestros)
# Qué hace: UPDATE table SET company_id = NULL WHERE id IN (...)
# Modelos: Contactos, Productos. Esto los hace "multi-company" por defecto.


MODEL_STRATEGY = {
    # --- VENTAS, COMPRAS Y CRM (MOVE TO PARENT) ---
    "sale.order": "MOVE_TO_PARENT",
    "sale.order.line": "MOVE_TO_PARENT",
    "sale.order.template": "MOVE_TO_PARENT",
    "sale.order.type": "MOVE_TO_PARENT",
    "purchase.order": "MOVE_TO_PARENT",
    "purchase.order.line": "MOVE_TO_PARENT",
    "purchase.requisition": "MOVE_TO_PARENT",
    "purchase.subscription": "MOVE_TO_PARENT",
    "purchase.request": "MOVE_TO_PARENT",
    "purchase.request.line": "MOVE_TO_PARENT",
    "crm.lead": "MOVE_TO_PARENT",
    "crm.team": "MOVE_TO_PARENT",
    "utm.campaign": "MOVE_TO_PARENT",
    # --- STOCK E INVENTARIO (MOVE TO PARENT) ---
    "stock.picking": "MOVE_TO_PARENT",
    "stock.picking.type": "MOVE_TO_PARENT",
    "stock.move": "MOVE_TO_PARENT",
    "stock.move.line": "MOVE_TO_PARENT",
    "stock.quant": "MOVE_TO_PARENT",
    "stock.valuation.layer": "MOVE_TO_PARENT",
    "stock.lot": "MOVE_TO_PARENT",
    "stock.warehouse": "MOVE_TO_PARENT",
    "stock.location": "MOVE_TO_PARENT",
    "stock.scrap": "MOVE_TO_PARENT",
    "stock.landed.cost": "MOVE_TO_PARENT",
    "stock.warehouse.orderpoint": "MOVE_TO_PARENT",
    "stock.putaway.rule": "MOVE_TO_PARENT",
    "stock.route": "MOVE_TO_PARENT",
    "stock.rule": "MOVE_TO_PARENT",
    "stock.package": "MOVE_TO_PARENT",
    # --- MANUFACTURA Y PROYECTOS (MOVE TO PARENT) ---
    "mrp.production": "MOVE_TO_PARENT",
    "mrp.bom": "MOVE_TO_PARENT",
    "mrp.bom.line": "MOVE_TO_PARENT",
    "mrp.workcenter": "MOVE_TO_PARENT",
    "mrp.unbuild": "MOVE_TO_PARENT",
    "project.project": "MOVE_TO_PARENT",
    "project.task": "MOVE_TO_PARENT",
    "helpdesk.team": "MOVE_TO_PARENT",
    "helpdesk.ticket": "MOVE_TO_PARENT",
    "repair.order": "MOVE_TO_PARENT",
    "quality.check": "MOVE_TO_PARENT",
    "quality.alert": "MOVE_TO_PARENT",
    "product.supplierinfo": "MOVE_TO_PARENT",
    # --- CONTABILIDAD OPERATIVA (KEEP AND CHECK - Se quedan en la sucursal B) ---
    "account.move": "KEEP_AND_CHECK",
    "account.move.line": "KEEP_AND_CHECK",
    "account.payment": "KEEP_AND_CHECK",
    "account.bank.statement": "KEEP_AND_CHECK",
    "account.bank.statement.line": "KEEP_AND_CHECK",
    "account.batch.payment": "KEEP_AND_CHECK",
    "account.partial.reconcile": "KEEP_AND_CHECK",
    "account.asset": "KEEP_AND_CHECK",
    "account.loan": "KEEP_AND_CHECK",
    "l10n_latam.check": "KEEP_AND_CHECK",
    "account.cashbox.session": "KEEP_AND_CHECK",
    "account.payment.receiptbook": "KEEP_AND_CHECK",
    "account.journal": "KEEP_AND_CHECK",
    # --- CONFIGURACIÓN CONTABLE (MERGE OR MOVE) ---
    # TODOS LOS MERGE_OR_MOVE son consistentes con que son compartidos de padre a hijos	[('company_id', 'parent_of', company_ids)]
    # por lo cual unirlos o moverlos debería ser seguro.
    "account.tax": "MERGE_OR_MOVE",
    "account.tax.group": "MERGE_OR_MOVE",
    "account.fiscal.position": "MERGE_OR_MOVE",
    "account.analytic.account": "MERGE_OR_MOVE",
    "account.group": "MERGE_OR_MOVE",
    "account.payment.term": "MERGE_OR_MOVE",
    "account.reconcile.model": "MERGE_OR_MOVE",
    "account.analytic.applicability": "MERGE_OR_MOVE",
    "account.analytic.distribution.model": "MERGE_OR_MOVE",
    "account.analytic.line": "MERGE_OR_MOVE",
    "account.journal.group": "MERGE_OR_MOVE",
    "account.fiscal.position.account": "MERGE_OR_MOVE",
    "account.tax.repartition.line": "MERGE_OR_MOVE",
    # --- MAESTROS (KEEP - No tocamos company_id porque ya funcionaban) ---
    "res.partner": "KEEP",
    "res.company": "KEEP",
    "ir.default": "KEEP",
    "product.template": "KEEP",
    "product.product": "KEEP",
    "product.pricelist": "KEEP",
    "product.category": "KEEP",
    "res.users": "KEEP",
    "res.partner.bank": "KEEP",
    # res.currency HAY QUE VER. NO PUEDO CREAR MONEDA EN SUCURSALES! HAY VER SI LO PERMITIMOS A NIVEL PRODUCTO --> NOS FACILITA LA VIDA
    "res.currency": "KEEP",
    "res.currency.rate": "KEEP",
    "onboarding.progress": "KEEP",
    "onboarding.progress.step": "KEEP",
    "resource.calendar": "KEEP",
    "resource.calendar.leaves": "KEEP",
    "resource.resource": "KEEP",
    "certificate.key": "KEEP",
    "certificate.certificate": "KEEP",
    "product.combo": "KEEP",
    "product.combo.item": "KEEP",
    "product.pricelist.item": "KEEP",
    "payment.transaction": "KEEP",
    "payment.token": "KEEP",
    "payment.provider": "KEEP",
    "digest.digest": "KEEP",
    "snailmail.letter": "KEEP",
    "account.lock_exception": "KEEP",
    "account.reconcile.model.line": "KEEP",
    "account.report.external.value": "KEEP",
    "account.invoice.report": "KEEP",
    # --- RRHH (KEEP AND CHECK) ---
    "hr.employee": "KEEP_AND_CHECK",
    "hr.contract": "KEEP_AND_CHECK",
    "hr.job": "KEEP_AND_CHECK",
    "hr.department": "KEEP_AND_CHECK",
    "hr.leave": "KEEP_AND_CHECK",
    "hr.applicant": "KEEP_AND_CHECK",
    # --- OTROS (MOVE TO PARENT) ---
    "account.account": "MOVE_TO_PARENT",
    "mail.activity.plan": "MOVE_TO_PARENT",
    "documents.document": "MOVE_TO_PARENT",
    "loyalty.program": "MOVE_TO_PARENT",
    "loyalty.card": "MOVE_TO_PARENT",
    "event.event": "MOVE_TO_PARENT",
    "website": "MOVE_TO_PARENT",
    "ir.sequence": "MOVE_TO_PARENT",
    "ir.attachment": "KEEP_AND_CHECK",  # As you can have attachments from a account move model than need to be kept in the same company
    # as originally they were.
}


def is_integer_column(cr, table_name, column_name):
    """Check if a column is of integer or bigint type (not JSONB, etc)."""
    cr.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """,
        (table_name, column_name),
    )
    result = cr.fetchone()
    return result and result[0] in ("integer", "bigint")


def table_exists(cr, table_name):
    """Check if a table exists in the database."""
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name=%s
              AND table_type = 'BASE TABLE'
        )
    """,
        (table_name,),
    )
    return cr.fetchone()[0]


def handle_merge_or_move(env, model_name, id_a, id_b):
    """
    Intenta fusionar registros de B en A si son equivalentes.
    Si no hay equivalente, mueve el registro a la compañía A.
    """
    Model = env[model_name]
    cr = env.cr
    # Verificar si el modelo usa company_id o company_ids
    if "company_ids" in Model._fields:
        records_b = Model.with_context(active_test=False).search(
            [("company_ids", "in", [id_b])]
        )
        company_domain = [("company_ids", "in", [id_a])]
    else:
        records_b = Model.with_context(active_test=False).search(
            [("company_id", "=", id_b)]
        )
        company_domain = [("company_id", "=", id_a)]

    criteria_fields = MERGE_CRITERIA.get(
        model_name, ["name"]
    )  # Por defecto, intentamos usar 'name' o 'display_name' como criterio de equivalencia

    def _move_record_to_parent(record):
        if "company_ids" in Model._fields:
            # Para many2many, reemplazar la compañía B por A
            record._write({"company_ids": [(3, id_b), (4, id_a)]})
        else:
            record._write({"company_id": id_a})

    for rec_b in records_b:
        # --- CASO account.tax.group: eliminar si no tiene impuestos asociados y no tiene campo active ---
        if model_name == "account.tax.group":
            # Si no tiene campo active y no tiene impuestos asociados, eliminar
            has_active = "active" in rec_b._fields
            taxes = (
                env["account.tax"]
                .with_context(active_test=False)
                .search([("tax_group_id", "=", rec_b.id)])
            )
            if not has_active and not taxes:
                _logger.info(
                    f"ELIMINANDO account.tax.group '{rec_b.display_name}' (B) sin impuestos asociados y sin campo active"
                )
                rec_b.unlink()
                continue

        # --- Construir dominio de búsqueda para el equivalente en A ---
        domain = company_domain.copy()
        valid_criteria = True

        # Para account.tax, buscar por tax_group además de los criterios
        if model_name == "account.tax":
            # Buscar por tax_group primero si existe
            if rec_b.tax_group_id:
                domain.extend(
                    [
                        "|",
                        ("tax_group_id.name", "=", rec_b.tax_group_id.name),
                        ("name", "=", rec_b.name),
                    ]
                )

        for field in criteria_fields:
            if field not in rec_b._fields:
                valid_criteria = False
                break

            field_value = getattr(rec_b, field, None)
            if field_value is not None:
                domain.append((field, "=", field_value))

        # Search UNA sola vez, fuera del loop, con el dominio completo
        rec_a = (
            Model.with_context(active_test=False).search(domain, limit=1)
            if valid_criteria
            else False
        )
        if rec_a:
            # Para impuestos inactivos, priorizamos moverlos a la matriz para no dejarlos en la sucursal.
            if (
                model_name == "account.tax"
                and "active" in rec_b._fields
                and not rec_b.active
            ):
                _logger.info(
                    "MOVIENDO INACTIVO: %s '%s' (B) -> compañía A",
                    model_name,
                    rec_b.display_name,
                )
                _move_record_to_parent(rec_b)
                continue

            if "active" in rec_b._fields and not rec_a.active:
                rec_a.active = True
            _logger.info(
                f"FUSIONANDO: {model_name} '{rec_b.display_name}' (B) -> '{rec_a.display_name}' (A)"
            )

            # Re-mapear FK antes de archivar
            fk_fields = env["ir.model.fields"].search(
                [
                    ("relation", "=", model_name),
                    ("ttype", "=", "many2one"),
                    ("store", "=", True),
                    ("model_id.transient", "=", False),
                    ("model_id.abstract", "=", False),
                ]
            )
            for fk in fk_fields:
                fk_table = fk.model.replace(".", "_")
                if table_exists(cr, fk_table):
                    if is_integer_column(cr, fk_table, fk.name):
                        _logger.info(
                            "Re-mapeando FK: %s.%s id=%s -> id=%s",
                            fk.model,
                            fk.name,
                            rec_b.id,
                            rec_a.id,
                        )
                        cr.execute(
                            f"UPDATE {fk_table} SET {fk.name} = %s WHERE {fk.name} = %s",
                            (rec_a.id, rec_b.id),
                        )
                    else:
                        _logger.info(
                            "Saltando FK: %s.%s porque la columna no es integer",
                            fk.model,
                            fk.name,
                        )
                else:
                    _logger.info(
                        "Saltando FK: %s.%s porque la tabla %s no existe",
                        fk.model,
                        fk.name,
                        fk_table,
                    )

            if "name" in rec_b._fields:
                rec_b.name = f"[DEPRECATED-{rec_b.id}] {rec_b.name}"
            if "active" in rec_b._fields:
                rec_b.active = False  # Archivamos el de B para que no moleste
        else:
            # No hay equivalente, simplemente lo movemos a la matriz
            _logger.info(f"MOVIENDO: {model_name} '{rec_b.display_name}' a compañía A")
            _move_record_to_parent(rec_b)


def check_consistency_keep(env, model_name, id_b):
    """Valida registros que se quedan en la sucursal"""
    Model = env[model_name]
    # Buscamos registros en B que tengan campos Many2one apuntando a objetos
    # que Odoo 19 podría considerar inválidos (si no son parte de la jerarquía)
    records = Model.search([("company_id", "=", id_b)])
    if records:
        _logger.info(
            f"CHECK: {len(records)} registros de {model_name} validados en sucursal {id_b}"
        )
        # Aquí se podría disparar un Model._check_company() si fuera necesario
        # Por ahora logueamos la permanencia exitosa.


def migrate_json_company_dependent(cr, env, id_a, id_b):
    """Busca y migra campos JSONB company_dependent"""
    id_a_str = str(id_a)
    id_b_str = str(id_b)

    # Campos que se copian de B a A pero NO se limpian de B
    # (necesarios en ambas compañías)
    COPY_ONLY_FIELDS = {
        "product.template": [
            "property_cost_method",
            "property_valuation",
            "standard_price",
        ],
        "product.product": ["standard_price"],
    }

    # 1. Buscar todos los campos company_dependent registrados
    dependent_fields = env["ir.model.fields"].search(
        [("company_dependent", "=", True), ("store", "=", True)]
    )

    # Agrupamos por modelo para hacer un solo UPDATE por tabla
    model_map = {}
    field_type_map = {}
    for f in dependent_fields:
        model_map.setdefault(f.model, []).append(f.name)
        field_type_map[(f.model, f.name)] = f.ttype

    for model_name, field_names in model_map.items():
        table = model_name.replace(".", "_")

        # Odoo 19 guarda estos campos como JSONB
        for field_name in field_names:
            field_type = field_type_map.get((model_name, field_name))

            # Determinar si este campo debe ser copiado sin limpiar
            copy_only = field_name in COPY_ONLY_FIELDS.get(model_name, [])

            if copy_only:
                # Solo copiar de B a A (sin eliminar B)
                _logger.info(f"Copiando JSONB (sin limpiar): {model_name}.{field_name}")
                query = f"""
                    UPDATE {table}
                    SET {field_name} = jsonb_set(
                        COALESCE({field_name}, '{{}}'::jsonb),
                        '{{{id_a_str}}}',
                        {field_name}->'{id_b_str}'
                    )
                    WHERE ({field_name} ? '{id_b_str}')
                      AND NOT ({field_name} ? '{id_a_str}');
                """
                cr.execute(query)
            elif field_type == "many2one":
                # Many2one: copiar de B a A y eliminar B
                _logger.info(f"Migrando JSONB many2one: {model_name}.{field_name}")
                query = f"""
                    UPDATE {table}
                    SET {field_name} = (
                        CASE
                            WHEN ({field_name} ? '{id_b_str}') AND NOT ({field_name} ? '{id_a_str}')
                            THEN jsonb_set({field_name}, '{{{id_a_str}}}', {field_name}->'{id_b_str}')
                            ELSE {field_name}
                        END
                    ) - '{id_b_str}'
                    WHERE {field_name} ? '{id_b_str}';
                """
                cr.execute(query)
            else:
                # Otros tipos de campo: no hacer nada
                _logger.info(
                    f"Saltando JSONB ({field_type}): {model_name}.{field_name}"
                )


def get_next_available_code(env, code, exclude_account_id=None):
    """Devuelve un código libre validando contra todas las cuentas visibles por sudo."""
    Account = env["account.account"].sudo().with_context(active_test=False)
    base_code = code
    candidate = base_code
    suffix = 1

    while True:
        domain = [("code", "=", candidate)]
        if exclude_account_id:
            domain.append(("id", "!=", exclude_account_id))

        if not Account.search_count(domain):
            return candidate

        candidate = f"{base_code}.{suffix}"
        suffix += 1


def merge_accounts_by_code(env, id_a):
    """Fusiona cuentas contables con mismo code dentro de la compañía destino."""
    Account = env["account.account"].with_context(active_test=False)
    accounts = Account.with_context(allowed_company_ids=[id_a]).search(
        [
            ("company_ids", "in", [id_a]),
            ("company_ids.active", "=", True),
            ("code", "!=", False),
        ],
        order="code, id",
    )

    grouped_accounts = {}
    for account in accounts:
        grouped_accounts.setdefault(account.code, env["account.account"])
        grouped_accounts[account.code] |= account

    merged_groups = 0
    for code, duplicate_accounts in grouped_accounts.items():
        if len(duplicate_accounts) <= 1:
            continue

        # No mergear si hay discrepancia en currency_id (una tiene moneda y otra no, o tienen monedas distintas)
        currencies = {acc.currency_id for acc in duplicate_accounts}
        if len(currencies) > 1:
            _logger.warning(
                "SALTANDO MERGE de cuentas con code=%s (ids=%s): discrepancia en currency_id (%s), renombrando todas salvo la de menor id con sufijo .1",
                code,
                duplicate_accounts.ids,
                [c.name or "sin moneda" for c in currencies],
            )
            keeper = duplicate_accounts.sorted("id")[0]
            for acc in duplicate_accounts.filtered(lambda a: a.id != keeper.id):
                new_code = get_next_available_code(
                    env, acc.code, exclude_account_id=acc.id
                )
                _logger.info(
                    "Renombrando cuenta id=%s: code '%s' -> '%s'",
                    acc.id,
                    acc.code,
                    new_code,
                )
                acc.write({"code": new_code})
            continue

        _logger.info(
            "FUSIONANDO CUENTAS: code=%s, ids=%s",
            code,
            duplicate_accounts.ids,
        )
        wizard = (
            env["account.merge.wizard"]
            .with_context(
                {
                    "allowed_company_ids": [id_a],
                    "active_model": "account.account",
                    "active_ids": duplicate_accounts.ids,
                }
            )
            .create({"is_group_by_name": False})
        )
        wizard._action_merge(duplicate_accounts)
        merged_groups += 1

    _logger.info("Merge por código finalizado. Grupos fusionados: %s", merged_groups)


# ============================================================================
# STORE TO BRANCH MIGRATION FUNCTIONS
# ============================================================================


def table_exists(cr, table_name):
    """Check if a table exists in the database."""
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        )
    """,
        (table_name,),
    )
    return cr.fetchone()[0]


# def rebuild_store_mapping_from_backup(cr, env, parent_company_id, branch_company_ids):
#     """
#     Reconstruye el mapeo {store_id: company_id} desde la tabla de backup res_store_bu.

#     Se usa en vez de guardar este mapeo en el parámetro de sistema.
#     La tabla res_store_bu fue creada por el pre-migration script antes de que
#     el módulo base_multi_store fuera deprecado.

#     Returns:
#         dict: {store_id: company_id}
#     """
#     if not table_exists(cr, "res_store_bu"):
#         _logger.warning(
#             "Table res_store_bu not found. Run pre-migration script first."
#         )
#         return {}

#     Company = env["res.company"]
#     store_to_company = {}

#     # Leer todos los stores desde el backup, empezando por los que no tienen parent
#     cr.execute(
#         "SELECT id, name, parent_id, company_id FROM res_store_bu ORDER BY parent_id NULLS FIRST"
#     )
#     stores_data = cr.fetchall()  # [(id, name, parent_id, company_id), ...]

#     if not stores_data:
#         return {}

#     # El store parent es el primero sin parent_id
#     parent_store = next((s for s in stores_data if s[2] is None), stores_data[0])
#     store_to_company[parent_store[0]] = parent_company_id

#     for store_id, store_name, store_parent_id, store_original_company_id in stores_data:
#         if store_id in store_to_company:
#             continue

#         # Si el store tenía company_id y esa company es una de las branches, usarla
#         if store_original_company_id and store_original_company_id in branch_company_ids:
#             store_to_company[store_id] = store_original_company_id
#             _logger.info(
#                 "Mapping store %s ('%s') -> company %s (from original company_id)",
#                 store_id, store_name, store_original_company_id,
#             )
#             continue

#         # Buscar company por nombre entre las branches
#         company = Company.search(
#             [("name", "=", store_name), ("id", "in", branch_company_ids)], limit=1
#         )
#         if company:
#             store_to_company[store_id] = company.id
#             _logger.info(
#                 "Mapping store %s ('%s') -> company %s '%s' (by name)",
#                 store_id, store_name, company.id, company.name,
#             )
#         else:
#             # Fallback: usar parent company
#             store_to_company[store_id] = parent_company_id
#             _logger.warning(
#                 "Could not find matching company for store '%s', mapping to parent company",
#                 store_name,
#             )

#     return store_to_company


def get_store_to_company_mapping(env):
    """
    Crea o encuentra el mapeo entre stores y companies.

    El parámetro guardado solo contiene {'a': parent_id, 'b': [branch_ids]}.
    El store_mapping ({store_id: company_id}) se reconstruye en runtime desde
    res_store_bu para no almacenar datos derivados en el parámetro.

    Reglas:
    - La company parent (A) es la que NO tiene parent_id
    - Cada store de res_store_bu genera o reutiliza una res.company branch

    Returns:
        dict: {'a': parent_id, 'b': [branch_ids], 'store_mapping': {store_id: company_id}}
    """
    cr = env.cr

    # La tabla de origen puede ser res_store_bu (si aún existe) o res_store_bu (backup)
    source_table = None
    if table_exists(cr, "res_store_bu"):
        source_table = "res_store_bu"
    else:
        return {}

    Company = env["res.company"]

    # Intentar obtener el mapeo base guardado (solo 'a' y 'b')
    saved_mapping = safe_eval(
        env["ir.config_parameter"]
        .sudo()
        .get_param("migration_19_end_store_to_branch", "{}")
    )

    if saved_mapping:
        return saved_mapping

    # ---- Primera ejecución: construir el mapping ----

    # Leer stores desde la tabla fuente via SQL (funciona aunque el modelo ya no exista)
    cr.execute(
        f"SELECT id, name, parent_id, company_id FROM {source_table} ORDER BY parent_id NULLS FIRST"
    )
    stores_data = cr.fetchall()  # [(id, name, parent_id, company_id), ...]

    if not stores_data:
        return {}

    # Identificar la company parent (la que no tiene parent_id)
    parent_company = Company.search(
        [("parent_id", "=", False), ("active", "=", True)], limit=1
    )
    if not parent_company:
        parent_company = Company.search([("active", "=", True)], limit=1)
    if not parent_company:
        raise UserError("No se encontró una compañía activa para usar como parent")

    _logger.info(
        "Parent company identified: %s (ID: %s)", parent_company.name, parent_company.id
    )

    store_to_company = {}
    branch_company_ids = []

    # El store parent es el primero sin parent_id
    parent_store = next((s for s in stores_data if s[2] is None), stores_data[0])
    store_to_company[parent_store[0]] = parent_company.id
    _logger.info(
        "Mapping parent store '%s' (ID: %s) -> parent company '%s' (ID: %s)",
        parent_store[1],
        parent_store[0],
        parent_company.name,
        parent_company.id,
    )

    for store_id, store_name, store_parent_id, store_original_company_id in stores_data:
        if store_id in store_to_company:
            continue

        # Buscar company existente por nombre
        existing_company = Company.search([("name", "=", store_name)], limit=1)

        if existing_company:
            store_to_company[store_id] = existing_company.id
            branch_company_ids.append(existing_company.id)
            _logger.info(
                "Found existing company '%s' for store '%s'",
                existing_company.name,
                store_name,
            )
        else:
            # Determinar parent de la nueva branch
            company_parent_id = parent_company.id
            if store_parent_id and store_parent_id in store_to_company:
                company_parent_id = store_to_company[store_parent_id]

            new_company = Company.with_context(no_chart_of_accounts=True).create(
                {
                    "name": store_name,
                    "parent_id": company_parent_id,
                    "currency_id": parent_company.currency_id.id,
                    'l10n_ar_afip_responsibility_type_id': parent_company.l10n_ar_afip_responsibility_type_id.id,
                }
            )
            store_to_company[store_id] = new_company.id
            branch_company_ids.append(new_company.id)
            _logger.info(
                "Created new branch company '%s' (ID: %s) for store '%s' (ID: %s)",
                new_company.name,
                new_company.id,
                store_name,
                store_id,
            )

    # Guardar SOLO 'a' y 'b' en el parámetro (store_mapping se reconstruye desde res_store_bu)
    base_mapping = {"a": parent_company.id, "b": branch_company_ids}
    env["ir.config_parameter"].sudo().set_param(
        "migration_19_end_store_to_branch", str(base_mapping)
    )
    _logger.info("Saved base mapping to parameter: %s", base_mapping)

    # Incluir store_mapping en retorno (solo para esta ejecución)
    return base_mapping


def migrate_store_fields_to_company(cr, env, mapping):
    """
    Migra todos los campos store_id a company_id según el mapeo.

    Args:
        mapping: dict {'a': parent_id, 'b': [branch_ids], 'store_mapping': {store_id: company_id}}
                 store_mapping se reconstruye en runtime desde res_store_bu, no se persiste.
    """

    # Buscar todos los campos que apuntan a res.store
    store_fields = env["ir.model.fields"].search(
        [
            ("relation", "=", "res.store"),
            ("store", "=", True),
            ("model_id.transient", "=", False),
            ("model_id.abstract", "=", False),
        ]
    )

    # Modelos procesados para no duplicar esfuerzos
    processed_models = set()

    for field in store_fields:
        model_name = field.model
        table = model_name.replace(".", "_")
        field_name = field.name

        if model_name in processed_models:
            continue

        # Verificar que el modelo existe
        try:
            Model = env[model_name]
            if not Model._auto:
                continue
        except KeyError:
            _logger.warning(f"Model {model_name} not found, skipping")
            continue

        # Verificar si el modelo tiene company_id
        if "company_id" not in Model._fields:
            _logger.info(f"Model {model_name} has {field_name} but no company_id field")
            continue

        # Para cada store, actualizar los registros
        for store_id in mapping["b"]:
            store_id =  env['res.company'].browse(store_id)
            company_id = env['res.company'].browse(mapping["a"])
            if field.ttype == "many2one":
                # Verificar si el campo es related o computed
                field_obj = Model._fields.get(field_name)

                # Si es un campo related, no lo tocamos en SQL (se recomputará)
                if field_obj and field_obj.related:
                    _logger.info(
                        f"  Skipping related field {field_name}, will be recomputed"
                    )
                    continue

                # Actualizar company_id basado en store_id
                # Solo actualizamos si:
                # 1. El store_id coincide
                # 2. El company_id está vacío o es diferente al target
                query = f"""
                    UPDATE {table}
                    SET company_id = %s
                    WHERE store_id in ( SELECT id FROM res_store_bu WHERE name ilike %s)
                    AND (company_id IS NULL OR company_id != %s)
                """
                cr.execute(query, (store_id.id, store_id.name, store_id.id))

                if cr.rowcount > 0:
                    _logger.info(
                        f"  Updated {cr.rowcount} records for store {store_id.name} -> company {company_id.name}"
                    )

            elif field.ttype == "many2many":
                # Para many2many, esto es más complejo
                # Por ahora lo saltamos ya que store_id suele ser many2one
                _logger.info(
                    f"  Skipping many2many field {field_name} (not commonly used for stores)"
                )

        processed_models.add(model_name)

    # Invalidar y recomputar campos related que dependen de store_id
    _logger.info("Invalidating and recomputing related store fields")

    # Modelos comunes con campos related de store
    models_to_recompute = [
        "sale.order",  # store_id related to warehouse_id.store_id
        "purchase.order",  # store_id related to picking_type_id.store_id
        "account.move",  # store_id related to journal_id.store_id
        "account.payment",  # store_id related to journal_id.store_id
    ]

    for model_name in models_to_recompute:
        if model_name not in env:
            continue

        Model = env[model_name]
        if "store_id" in Model._fields:
            _logger.info(f"  Recomputing store_id for {model_name}")
            records = Model.search([])
            if records:
                records.invalidate_recordset(["store_id"])
                # No forzamos el compute aquí, se hará cuando se acceda


def migrate_store_to_branch(cr, env):
    """
    Función principal para migrar de multi-store a multi-company branches.

    Esta migración es para casos donde:
    - Se tenía 1 compañía con múltiples stores (res.store)
    - Se quiere migrar a múltiples companies en jerarquía (branches)

    Pasos:
    1. Mapear stores a companies (crear si es necesario)
    2. Establecer jerarquía de companies
    3. Migrar campos store_id a company_id
    4. Fusionar configuración contable (impuestos, cuentas) en parent
    5. Mantener apuntes contables en sus branches
    """
    mapping = safe_eval(
        env["ir.config_parameter"]
        .sudo()
        .get_param("migration_19_end_store_to_branch", "{}")
    )

    parent_company_id = mapping["a"]
    branch_company_ids = mapping["b"]


    Company = env["res.company"]
    parent_company = Company.browse(parent_company_id)

    _logger.info("Parent company: %s (ID: %s)", parent_company.name, parent_company_id)
    _logger.info("Branch companies: %s", branch_company_ids)

    for store_id in branch_company_ids:
        store_id = Company.browse(store_id)
        company = Company.browse(parent_company_id)

        # Establecer parent_id basado en la jerarquía de stores
        if not store_id.parent_id and company.id != store_id.company_id:
            store_id._write({"parent_id": parent_company_id})

    # 3. Migrar campos store_id a company_id
    _logger.info("Migrating store_id fields to company_id")
    migrate_store_fields_to_company(cr, env, mapping)
    cr.commit()

    # 4. Recalcular parent_path para todas las companies
    _logger.info("Recalculating company parent_path")
    Company._parent_store_compute()
    cr.commit()

    # 5. Fusionar/mover configuración contable a la parent company
    # Para stores, queremos que los impuestos, cuentas, etc. queden en la parent
    _logger.info(
        "Processing accounting configuration (taxes, accounts, fiscal positions)"
    )

    # Procesar MERGE_OR_MOVE para cada branch
    for branch_company_id in branch_company_ids:
        branch_company = Company.browse(branch_company_id)
        _logger.info(
            f"Processing configuration from branch '{branch_company.name}' to parent"
        )

        # Fusionar impuestos, posiciones fiscales, etc.
        merge_models = [m for m, s in MODEL_STRATEGY.items() if s == "MERGE_OR_MOVE"]

        for model_name in merge_models:
            try:
                handle_merge_or_move(
                    env, model_name, parent_company_id, branch_company.id
                )
            except Exception as e:
                _logger.warning(
                    f"Could not merge {model_name} from {branch_company.name}: {e}"
                )

        cr.commit()

    # 6. Archivar cuentas de las branches (opcional, dependiendo de la estrategia)
    # Por ahora no archivamos, las dejamos activas en sus branches

    # 7. Dar acceso a los usuarios a las branches que antes tenían vía store_ids
    _logger.info("Migrating user company access from store_ids to branch companies")
    migrate_store_user_access_to_company(cr, env, mapping)
    cr.commit()

    return parent_company.id


def migrate_store_user_access_to_company(cr, env, mapping):
    """
    Asigna a cada usuario acceso (company_ids) a las branches que antes
    tenía disponibles mediante el campo store_ids.

    Lee la tabla res_store_user_rel_bu creada por el pre-migration script,
    obtiene el store_mapping del mapping reconstruido en runtime y agrega
    las companies correspondientes al campo company_ids de cada usuario.
    """

    if not table_exists(cr, "res_store_bu"):
        _logger.warning(
            "Backup table res_store_bu not found. "
            "Skipping user access migration because store mapping cannot be rebuilt."
        )
        return

    cr.execute(
        """
        SELECT
            rsu.user_id as user_id,
            rc.id as company_id
        FROM res_store_users_rel_bu rsu
        JOIN res_store_bu rs
            ON rs.id = rsu.cid
        JOIN res_company rc
            ON rs.name = rc.name;
        """
    )
    user_company_rows = cr.fetchall()  # [(user_id, company_id), ...]
    if not user_company_rows:
        _logger.info("No stores found in backup, skipping user access migration")
        return

    # Agrupar company_ids por usuario a partir de la query (user_id, company_id)
    user_to_new_companies = {}
    for user_id, company_id in user_company_rows:
        if not user_id or not company_id:
            continue
        user_to_new_companies.setdefault(int(user_id), set()).add(int(company_id))

    Users = env["res.users"]
    migrated = 0
    for user_id, company_ids_to_add in user_to_new_companies.items():
        user = Users.browse(user_id).exists()
        if not user:
            _logger.warning("User ID %s not found, skipping", user_id)
            continue

        current_company_ids = set(user.company_ids.ids)
        new_company_ids = company_ids_to_add - current_company_ids

        if new_company_ids:
            _logger.info(
                "Granting user '%s' (ID: %s) access to companies: %s",
                user.name,
                user_id,
                list(new_company_ids),
            )
            user.write({"company_ids": [(4, cid) for cid in new_company_ids]})
            migrated += 1
        else:
            _logger.info(
                "User '%s' already has access to all their stores' companies, skipping",
                user.name,
            )

    _logger.info(
        "User access migration complete: %s users updated out of %s",
        migrated,
        len(user_to_new_companies),
    )


# ============================================================================
# ORIGINAL COMPANY MERGE MIGRATION FUNCTIONS
# ============================================================================


def preprocess_unique_move_conflicts(cr, model_name, id_a, id_b):
    """Resuelve colisiones conocidas antes de mover registros de compañía."""
    queries = UNIQUE_MOVE_PREPROCESSORS.get(model_name, ())
    for query in queries:
        _logger.info("Preprocesando colisiones UNIQUE para %s", model_name)
        # Contar cuántos placeholders %s tiene la query
        param_count = query.count("%s")
        # Pasar los parámetros correctos según la cantidad
        if param_count == 2:
            cr.execute(query, (id_b, id_a))
        elif param_count == 3:
            cr.execute(query, (id_b, id_a, id_a))
        else:
            _logger.warning(
                f"Query con {param_count} parámetros no soportada para {model_name}"
            )


# def sync_account_codes_sql(cr, rel_table, rel_account_col, rel_company_col, id_a, id_b):
#     """Sincroniza code_store de B hacia A para cuentas ligadas a la sucursal B."""
#     cr.execute(
#         f"""
#             UPDATE account_account aa
#                SET code_store = jsonb_set(
#                     COALESCE(aa.code_store, '{{}}'::jsonb),
#                     ARRAY[%s],
#                     aa.code_store->%s,
#                     true
#                )
#               FROM {rel_table} rel
#              WHERE rel.{rel_account_col} = aa.id
#                AND rel.{rel_company_col} = %s
#                AND aa.code_store ? %s
#         """,
#         (str(id_a), str(id_b), id_b, str(id_b)),
#     )


def migrate_standard_fields(cr, env, id_a, id_b):
    """Movimiento de campos Many2one/Many2many de compañía"""
    field_targets = env["ir.model.fields"].search(
        [
            ("relation", "=", "res.company"),
            ("store", "=", True),
            ("model_id.transient", "=", False),
            ("model_id.abstract", "=", False),
        ]
    )

    for field in field_targets:
        model_name = field.model
        table = model_name.replace(".", "_")
        strategy = MODEL_STRATEGY.get(model_name, "CHECK")

        # MERGE_OR_MOVE lo manejamos en método separado
        if strategy in ["KEEP", "MERGE_OR_MOVE"]:
            continue

        elif strategy == "KEEP_AND_CHECK":
            check_consistency_keep(env, model_name, id_b)
            continue

        elif strategy == "MOVE_TO_PARENT":
            if field.ttype == "many2one":
                if field.name == "company_id":
                    preprocess_unique_move_conflicts(cr, model_name, id_a, id_b)
                if (
                    field.name == "company_id"
                    and model_name in MODELS_WITH_UNIQUE_NAMES
                ):
                    cr.execute(
                        f"UPDATE {table} SET name = name || '-B' WHERE company_id = %s",
                        [id_b],
                    )
                cr.execute(
                    f"UPDATE {table} SET {field.name} = %s WHERE {field.name} = %s",
                    (id_a, id_b),
                )
            elif field.ttype == "many2many":
                rel_table = field.relation_table
                # if field.model == "account.account":
                #     sync_account_codes_sql(cr, rel_table, field.column1, field.column2, id_a, id_b)

                cr.execute(
                    f"""
                    UPDATE {rel_table}
                       SET {field.column2} = %s
                     WHERE {field.column2} = %s
                       AND {field.column1} NOT IN (
                            SELECT {field.column1}
                              FROM {rel_table}
                             WHERE {field.column2} = %s
                       )
                """,
                    (id_a, id_b, id_a),
                )
                cr.execute(
                    f"DELETE FROM {rel_table} WHERE {field.column2} = %s", (id_b,)
                )
        else:
            continue
            _logger.warning(
                f"Estrategia desconocida '{strategy}' para el modelo '{model_name}'"
            )


def create_mapping(cr):
    company_mapping = {}
    env = util.env(cr)
    query = """
    SELECT COUNT(*) AS sales_with_country_mismatch
    FROM sale_order so
    JOIN res_company rc_so
        ON rc_so.id = so.company_id
    WHERE EXISTS (
            SELECT 1
            FROM sale_order_line sol
            JOIN sale_order_line_invoice_rel rel
                ON rel.order_line_id = sol.id
            JOIN account_move_line aml
                ON aml.id = rel.invoice_line_id
            JOIN account_move inv
                ON inv.id = aml.move_id
            JOIN res_company rc_inv
                ON rc_inv.id = inv.company_id
            WHERE sol.order_id = so.id
              AND inv.move_type IN ('out_invoice', 'out_refund')
              AND sol.company_id
                  <> aml.company_id
      )"""
    cr.execute(query)
    result = cr.fetchone()
    if (
        result[0] > 0
        and len(
            env["stock.warehouse"]
            .search([("company_id", "!=", False)])
            .mapped("company_id")
            .filtered("active")
        )
        == 1
    ):
        if len(env["res.company"].search([])) != 2:
            raise UserError(
                'Hay más de dos companías y cruces, se debe configurar manualmente el mapeo de compañías con parametro "migration_19_end_multicompany".'
            )
        # Estos IDs deben ser parametrizables según el cliente
        id_empresa_b = (
            env["stock.warehouse"]
            .search([("company_id", "!=", False), ("company_id.active", "=", True)])
            .mapped("company_id")
        )
        id_empresa_a = env["res.company"].search([("id", "!=", id_empresa_b[0].id)])
        company_mapping = {"a": id_empresa_a[0].id, "b": id_empresa_b[0].id}
        env["ir.config_parameter"].sudo().set_param(
            "migration_19_end_multicompany", company_mapping
        )
    return company_mapping


def migrate(cr, version):
    env = util.env(cr)
    # Determinar el modo de migración
    store_mapping = (
        env["ir.config_parameter"].sudo().get_param("migration_19_end_store_to_branch")
    )
    company_mapping = safe_eval(env["ir.config_parameter"].sudo().get_param("migration_19_end_multicompany", "{}"))
    # ========================================================================
    # MODE 1: COMPANY MERGE (Two companies A and B -> B becomes branch of A)
    # ========================================================================
    if not store_mapping:
        if not company_mapping:
            company_mapping = create_mapping(cr)

        if not company_mapping:
            _logger.warning("No company mapping found, skipping migration")
            return

        id_a = company_mapping.get("a")
        ids_b = company_mapping.get("b")

        if not id_a or not ids_b:
            _logger.warning("Invalid company mapping, skipping migration")
            return

        if not isinstance(ids_b, (list, tuple)):
            ids_b = [ids_b]

        for id_b in ids_b:
            # 0. Establecer Jerarquía Branch
            cr.execute("UPDATE res_company SET parent_id = %s WHERE id = %s", (id_a, id_b))
            for id_b in ids_b:
                # 0. Establecer Jerarquía Branch
                cr.execute("UPDATE res_company SET parent_id = %s WHERE id = %s", (id_a, id_b))

                # 1. Movimiento Operativo (SQL)
                migrate_standard_fields(cr, env, id_a, id_b)

                # 2. Fusión de Configuración (ORM)
                merge_models = [m for m, s in MODEL_STRATEGY.items() if s == "MERGE_OR_MOVE"]
                for model_name in merge_models:
                    handle_merge_or_move(env, model_name, id_a, id_b)
                    cr.commit()

                # 3. Propiedades JSONB (SQL)
                migrate_json_company_dependent(cr, env, id_a, id_b)

                # 4. Limpieza: Archivar cuentas de la sucursal
                _logger.info("ARCHIVE: Desactivando cuentas contables de la sucursal B")
                env["account.account"].search([("company_ids", "=", id_b)]).write({"active": False})

                # 5. Recomputo correcto de parent_path, metodos y campos almacenados relacionados con la jerarquía de compañías
                env["res.company"].browse(id_b)._write({"parent_id": id_a})
                # 5.1. CRÍTICO: Recalcula parent_path para TODAS las compañías desde cero
                env["res.company"]._parent_store_compute()
                cr.commit()

            # 6. Fusiona cuentas contables
            merge_accounts_by_code(env, id_a)

            # 7.1. Recomputa campos stored en journals que dependen de la jerarquía
            journals = env["account.journal"].search([])
            journals.invalidate_recordset(["branch_order"])
            journals._compute_branch_order()
            journals.flush_recordset(["branch_order"])

            # 7.2. Recomputa shared_to_branches en payment method lines (related stored)
            pmls = env["account.payment.method.line"].search([])
            if "shared_to_branches" in pmls._fields:
                pmls.invalidate_recordset(["shared_to_branches"])
                pmls.flush_recordset(["shared_to_branches"])

        for warehouse in env["stock.warehouse"].search([]):
            for id_b in ids_b:
                if warehouse.partner_id.name  == env['res.company'].browse(id_b).name:
                    warehouse.partner_id = warehouse.company_id.partner_id
        env["account.journal"].search([]).write({"shared_to_branches": False})
        cr.commit()
    # ========================================================================
    # MODE 1: STORE TO BRANCH (Single company with multi-store -> Multi-company branches)
    # ========================================================================
    if not company_mapping:
        if not store_mapping or store_mapping == "{}":
            store_mapping = get_store_to_company_mapping(env)
            env.cr.commit()

        if not store_mapping:
            _logger.info("No store mapping found, skipping store-to-branch migration")
            return None

        _logger.info("Running STORE TO BRANCH migration")
        parent_company_id = migrate_store_to_branch(cr, env)

        if parent_company_id:
            # Después de migrar stores a branches, aplicar merge de cuentas
            merge_accounts_by_code(env, parent_company_id)

            # Recomputar campos relacionados con la jerarquía
            journals = env["account.journal"].search([])
            journals.invalidate_recordset(["branch_order"])
            journals._compute_branch_order()
            journals.flush_recordset(["branch_order"])

            pmls = env["account.payment.method.line"].search([])
            if "shared_to_branches" in pmls._fields:
                pmls.invalidate_recordset(["shared_to_branches"])
                pmls.flush_recordset(["shared_to_branches"])

            env["account.journal"].search([('company_id', '=', parent_company_id)]).write({"shared_to_branches": True})
            cr.commit()
