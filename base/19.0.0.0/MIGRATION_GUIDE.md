# Odoo 19 End-Migration Guide

## Overview

Este script de migración (`end-migration.py`) soporta **dos estrategias principales** para consolidar multi-company/multi-store en Odoo 19 usando el sistema de branches.

---

## Modo 1: STORE TO BRANCH

### Escenario
- **Origen**: Sistema con **1 compañía** y múltiples **stores** (`res.store` - módulo `ingadhoc-multi-store`)
- **Destino**: Sistema con **múltiples companies** en jerarquía (branches estilo Odoo 19)

### ¿Qué hace?

1. **Identifica la company parent (A)**
   - La company que NO tiene `parent_id`
   - Si todas tienen parent o ninguna, toma la primera activa

2. **Mapea cada `res.store` a una `res.company`**
   - Si el store ya tiene `company_id`, lo usa
   - Si existe una company con el mismo nombre, la reutiliza
   - Si no, crea una nueva company como branch

3. **Migra campos `store_id` → `company_id`**
   - Actualiza automáticamente todos los registros que tenían `store_id`
   - Modelos afectados: `sale.order`, `purchase.order`, `stock.warehouse`, `account.journal`, etc.

4. **Establece jerarquía de branches**
   - Respeta la jerarquía de `parent_id` entre stores
   - Recalcula `parent_path` automáticamente

5. **Consolida configuración contable en parent**
   - Impuestos (`account.tax`)
   - Posiciones fiscales (`account.fiscal.position`)
   - Términos de pago (`account.payment.term`)
   - Cuentas analíticas (`account.analytic.account`)
   - Grupos de cuentas (`account.group`)

6. **Mantiene apuntes contables en sus branches**
   - Facturas (`account.move`)
   - Pagos (`account.payment`)
   - Diarios (`account.journal`)
   - Estados de cuenta bancarios

### Configuración

Para **forzar** este modo:
```python
# En Odoo, crear parámetro de sistema:
env['ir.config_parameter'].sudo().set_param('migration_19_end_mode', 'store_to_branch')
```

Para **mapeo manual** (opcional):
```python
# Mapear store_id -> company_id manualmente
mapping = {
    1: 1,  # Store 1 -> Company 1
    2: 2,  # Store 2 -> Company 2
    3: 3,  # Store 3 -> Company 3
}
env['ir.config_parameter'].sudo().set_param('migration_19_end_store_to_branch', str(mapping))
```

### Estructura Resultante

```
Antes:
res.company (1)
  ├─ res.store "Sucursal A" (fields: store_id)
  ├─ res.store "Sucursal B"
  └─ res.store "Sucursal C"

Después:
res.company "Compañía Principal" (A)
  ├─ res.company "Sucursal A" (branch) (fields: company_id)
  ├─ res.company "Sucursal B" (branch)
  └─ res.company "Sucursal C" (branch)
```

---

## Modo 2: COMPANY MERGE

### Escenario
- **Origen**: Sistema con **2 compañías hermanas** (A y B)
- **Destino**: Sistema con jerarquía donde **B es branch de A**

### ¿Qué hace?

1. **Establece jerarquía**: B se convierte en hijo de A (`B.parent_id = A`)

2. **Aplica estrategias por tipo de dato**:

   - **MOVE_TO_PARENT** (Datos operativos)
     - Ventas, compras, CRM → se mueven a A
     - Stock, inventario → se mueven a A
     - Manufactura, proyectos → se mueven a A
   
   - **KEEP_AND_CHECK** (Datos financieros)
     - Facturas, pagos → se mantienen en B
     - Diarios contables → se mantienen en B
     - Estados de cuenta → se mantienen en B
   
   - **KEEP** (Maestros)
     - Contactos, productos → se mantienen compartidos
     - Monedas, listas de precios → se mantienen
   
   - **MERGE_OR_MOVE** (Configuración fiscal)
     - Impuestos → se fusionan o mueven a A
     - Posiciones fiscales → se fusionan o mueven a A
     - Cuentas contables → se fusionan por código

3. **Maneja campos company-dependent (JSONB)**
   - Migra valores de B a A en campos `company_dependent=True`
   - Elimina valores de B después de copiar

4. **Fusiona cuentas duplicadas**
   - Une cuentas con el mismo `code` dentro de A
   - Usa el wizard `account.merge.wizard`

### Configuración

Para **forzar** este modo:
```python
env['ir.config_parameter'].sudo().set_param('migration_19_end_mode', 'company_merge')
```

Para **configurar companies**:
```python
# Definir cuál es A (parent) y cuál es B (branch)
mapping = {
    'a': 1,  # ID de company parent
    'b': 2,  # ID de company que será branch
}
env['ir.config_parameter'].sudo().set_param('migration_19_end_multicompany', str(mapping))
```

### Detección Automática

El script detecta automáticamente el escenario cuando:
- Hay ventas (`sale.order`) con facturas (`account.move`) de diferentes companies
- Existe solo 1 warehouse activo
- Hay exactamente 2 companies

---

## Modo 3: AUTO (Default)

Si no se especifica `migration_19_end_mode`, el script **detecta automáticamente**:

1. **Busca tabla `res_store`**
   - Si existe y tiene datos → **STORE_TO_BRANCH**

2. **Busca mapping de companies**
   - Si existe parámetro `migration_19_end_multicompany` → **COMPANY_MERGE**
   - Si detecta escenario de 2 companies con cruces → **COMPANY_MERGE**

3. **No detecta nada**
   - No ejecuta ninguna migración
   - Loguea advertencia

---

## Estrategias de Migración (Detalle)

### MOVE_TO_PARENT
```sql
UPDATE model SET company_id = A WHERE company_id = B
```
Para: Datos operativos que deben consolidarse

### KEEP_AND_CHECK
```python
# No modifica company_id, solo valida parent_id
assert B.parent_id == A
```
Para: Datos financieros que deben permanecer en la branch

### KEEP
```python
# No hace nada
pass
```
Para: Maestros que ya están bien compartidos

### MERGE_OR_MOVE
```python
if exists_equivalent(record_B, in_company=A):
    merge(record_B, record_A)
    archive(record_B)
else:
    move(record_B, to_company=A)
```
Para: Configuración fiscal que debe unificarse

---

## Modelos Procesados

### Operativos (MOVE_TO_PARENT)
- `sale.order`, `sale.order.line`
- `purchase.order`, `purchase.order.line`
- `stock.picking`, `stock.move`, `stock.quant`
- `stock.warehouse`, `stock.location`
- `mrp.production`, `mrp.bom`
- `project.project`, `project.task`

### Financieros (KEEP_AND_CHECK)
- `account.move`, `account.move.line`
- `account.payment`
- `account.bank.statement`, `account.bank.statement.line`
- `account.journal`
- `l10n_latam.check`

### Configuración (MERGE_OR_MOVE)
- `account.tax`, `account.tax.group`
- `account.fiscal.position`
- `account.payment.term`
- `account.analytic.account`
- `account.group`

### Maestros (KEEP)
- `res.partner`
- `product.template`, `product.product`
- `product.pricelist`
- `res.currency`

---

## Ejecutar la Migración

### Desde Odoo Shell

```bash
# Conectar a Odoo Shell
odoo-bin shell -d DATABASE -c /path/to/odoo.conf

# Ejecutar migración manual
from odoo.upgrade import util
cr = env.cr
version = '19.0.0.0'

# Importar el módulo
import sys
sys.path.insert(0, '/path/to/odoo-upgrade/base/19.0.0.0')
from end_migration import migrate

# Ejecutar
migrate(cr, version)
```

### Durante Upgrade

El script se ejecuta automáticamente durante el upgrade a 19.0.0.0.

---

## Validación Post-Migración

### Verificar Jerarquía
```python
# Todas las branches deben tener parent_id
branches = env['res.company'].search([('parent_id', '!=', False)])
for branch in branches:
    assert branch.parent_id
    assert branch.parent_path
    print(f"✓ {branch.name} -> {branch.parent_id.name}")
```

### Verificar Cuentas
```python
# No debería haber cuentas duplicadas en la parent
parent = env['res.company'].search([('parent_id', '=', False)], limit=1)
accounts = env['account.account'].search([('company_ids', 'in', parent.ids)])
codes = accounts.mapped('code')
assert len(codes) == len(set(codes)), "Hay cuentas duplicadas!"
```

### Verificar Apuntes Contables
```python
# Los apuntes deben estar en sus branches
moves = env['account.move'].search([('move_type', 'in', ['out_invoice', 'in_invoice'])])
for move in moves:
    assert move.company_id.parent_id or move.company_id.id == parent.id
    print(f"✓ {move.name} en {move.company_id.name}")
```

### Verificar Journals
```python
# Journals deben tener branch_order correcto
journals = env['account.journal'].search([])
journals._compute_branch_order()
for journal in journals:
    print(f"{journal.name}: branch_order={journal.branch_order}")
```

---

## Rollback / Deshacer

⚠️ **IMPORTANTE**: Hacer backup ANTES de ejecutar la migración.

Para deshacer:
1. Restaurar backup de la base de datos
2. Revisar los parámetros de sistema creados:
   - `migration_19_end_mode`
   - `migration_19_end_store_to_branch`
   - `migration_19_end_multicompany`

---

## Logs

El script genera logs detallados:
- `INFO`: Operaciones normales
- `WARNING`: Situaciones que requieren atención
- `ERROR`: Errores críticos

Buscar en logs:
```bash
grep "STORE TO BRANCH" odoo.log
grep "COMPANY MERGE" odoo.log
grep "MIGRATION MODE" odoo.log
```

---

## FAQ

### ¿Qué pasa con los stores después de la migración?
Los stores (`res.store`) permanecen en la base de datos pero ya no se usan. Los campos `store_id` son reemplazados por `company_id`.

### ¿Se pierden datos?
No. Todos los datos se migran. Los apuntes contables, facturas y pagos se mantienen en sus branches correspondientes.

### ¿Puedo tener más de 2 companies?
Sí, en modo STORE_TO_BRANCH puedes migrar N stores a N branches.

### ¿Qué pasa si ya tengo branches configuradas?
El script respeta las branches existentes y solo migra/fusiona según sea necesario.

### ¿Puedo probar en QA primero?
**Sí, DEBES probar en QA primero**. Nunca ejecutes esto directamente en producción.

---

## Soporte

Para issues o preguntas:
1. Revisar los logs detallados
2. Verificar los parámetros de sistema
3. Contactar al equipo de upgrade

---

**Última actualización**: 2026-04-16
