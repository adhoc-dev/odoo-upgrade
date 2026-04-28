import logging

from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

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
                domain.extend([
                    "|",
                    ("tax_group_id.name", "=", rec_b.tax_group_id.name),
                    ("name", "=", rec_b.name),
                ])

        for field in criteria_fields:
            if field not in rec_b._fields:
                valid_criteria = False
                break

            field_value = getattr(rec_b, field, None)
            if field_value is not None:
                domain.append((field, "=", field_value))

        # Search UNA sola vez, fuera del loop, con el dominio completo
        rec_a = Model.with_context(active_test=False).search(domain, limit=1) if valid_criteria else False
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
                    _logger.info("Saltando FK: %s.%s porque la tabla %s no existe", fk.model, fk.name, fk_table)
            
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

    # 1. Buscar todos los campos company_dependent registrados
    dependent_fields = env["ir.model.fields"].search(
        [("company_dependent", "=", True), ("store", "=", True)]
    )

    # Agrupamos por modelo para hacer un solo UPDATE por tabla
    model_map = {}
    for f in dependent_fields:
        model_map.setdefault(f.model, []).append(f.name)

    for model_name, field_names in model_map.items():
        table = model_name.replace(".", "_")

        # Odoo 19 guarda estos campos como JSONB
        for field_name in field_names:
            _logger.info(f"Migrando JSONB: {model_name}.{field_name}")

            # SQL:
            # 1. Si existe clave B y NO existe clave A: Crear A con valor de B.
            # 2. Eliminar clave B.
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
    merge_accounts_needed = False

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
    company_mapping = safe_eval(
        env["ir.config_parameter"]
        .sudo()
        .get_param("migration_19_end_multicompany", "{}")
    )
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
        env["account.account"].search([("company_ids", "=", id_b)]).write(
            {"active": False}
        )

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
            if warehouse.partner_id.name == env["res.company"].browse(id_b).name:
                warehouse.partner_id = warehouse.company_id.partner_id
    env["account.journal"].search([]).write({"shared_to_branches": False})
    cr.commit()
