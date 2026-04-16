# Resumen de Cambios - end-migration.py (19.0.0.0)

## ✅ Cambios Implementados

### 1. **Nuevo Modo: STORE TO BRANCH**

Se agregó soporte completo para migrar desde sistemas multi-store (ingadhoc-multi-store) a multi-company branches de Odoo 19.

**Características principales:**
- Identificación automática de la company parent (la que NO tiene parent_id)
- Mapeo automático o manual de `res.store` → `res.company`
- Migración de campos `store_id` → `company_id` en todos los modelos
- Establecimiento de jerarquía de branches basada en jerarquía de stores
- Consolidación de configuración contable (impuestos, cuentas) en company parent
- Mantenimiento de apuntes contables en sus branches correspondientes

### 2. **Modo Original: COMPANY MERGE (Preservado)**

El modo original para fusionar 2 companies (A y B) se mantiene intacto y funcional.

### 3. **Detección Automática (AUTO Mode)**

El script ahora detecta automáticamente qué tipo de migración ejecutar:
- Si encuentra `res_store` con datos → ejecuta STORE_TO_BRANCH
- Si encuentra mapping de companies → ejecuta COMPANY MERGE
- Si no detecta nada → no hace migración

### 4. **Funciones Agregadas**

```python
# NUEVAS FUNCIONES:

table_exists(cr, table_name)
# Verifica si una tabla SQL existe

get_store_to_company_mapping(env)
# Crea/obtiene mapeo store_id -> company_id
# Guarda en: migration_19_end_store_to_branch

migrate_store_fields_to_company(cr, env, store_to_company_map)
# Migra todos los campos store_id a company_id
# Maneja campos related, computed y stored
# Respeta estrategias del MODEL_STRATEGY

migrate_store_to_branch(cr, env)
# Función principal de migración store->branch
# Coordina todo el proceso
```

### 5. **Función migrate() Renovada**

```python
def migrate(cr, version):
    # Ahora soporta 3 modos:
    # - store_to_branch
    # - company_merge
    # - auto (default)
```

### 6. **Documentación Completa**

Se agregó:
- Comentarios detallados en el código
- Archivo `MIGRATION_GUIDE.md` con guía completa de uso
- Ejemplos de configuración y validación

---

## 📋 Estructura del Script

```
end-migration.py
├─ [HEADER] Documentación y modos
├─ [CONSTANTS] MODEL_STRATEGY, MERGE_CRITERIA, etc.
├─ [STORE TO BRANCH]
│  ├─ table_exists()
│  ├─ get_store_to_company_mapping()
│  ├─ migrate_store_fields_to_company()
│  └─ migrate_store_to_branch()
├─ [COMPANY MERGE] (original)
│  ├─ handle_merge_or_move()
│  ├─ check_consistency_keep()
│  ├─ migrate_json_company_dependent()
│  ├─ migrate_standard_fields()
│  ├─ merge_accounts_by_code()
│  └─ create_mapping()
└─ [MAIN]
   └─ migrate() → auto-detect + routing
```

---

## 🎯 Casos de Uso

### Caso 1: Migración Multi-Store
```
ANTES:
- 1 Company
- 5 Stores (res.store) con jerarquía
- Todos los modelos usan store_id

DESPUÉS:
- 1 Company Parent
- 4 Companies Branch (una por cada store hijo)
- Todos los modelos usan company_id
- Configuración fiscal consolidada en parent
```

### Caso 2: Fusión de Companies (Original)
```
ANTES:
- Company A (principal)
- Company B (hermana)

DESPUÉS:
- Company A (parent)
- Company B (branch de A)
- Datos operativos en A
- Datos financieros en B
```

---

## ⚙️ Configuración

### Forzar Modo Store-to-Branch
```python
env['ir.config_parameter'].sudo().set_param(
    'migration_19_end_mode', 
    'store_to_branch'
)
```

### Mapeo Manual (Opcional)
```python
# Mapear cada store_id a su company_id destino
mapping = {
    1: 1,  # Store Central -> Company Principal
    2: 2,  # Store Norte -> Company Norte
    3: 3,  # Store Sur -> Company Sur
}
env['ir.config_parameter'].sudo().set_param(
    'migration_19_end_store_to_branch', 
    str(mapping)
)
```

---

## ✓ Lo que se MIGRA automáticamente

### Campos store_id → company_id en:
- ✓ `stock.warehouse.store_id`
- ✓ `account.journal.store_id`
- ✓ `sale.order.store_id` (related, se recomputa)
- ✓ `purchase.order.store_id` (related, se recomputa)
- ✓ `account.move.store_id` (related, se recomputa)
- ✓ `account.payment.store_id` (related, se recomputa)

### Configuración Contable (MERGE_OR_MOVE → Parent):
- ✓ Impuestos (`account.tax`)
- ✓ Grupos de impuestos (`account.tax.group`)
- ✓ Posiciones fiscales (`account.fiscal.position`)
- ✓ Términos de pago (`account.payment.term`)
- ✓ Cuentas analíticas (`account.analytic.account`)
- ✓ Grupos de cuentas (`account.group`)

### Datos que se MANTIENEN en Branches:
- ✓ Facturas (`account.move`)
- ✓ Apuntes contables (`account.move.line`)
- ✓ Pagos (`account.payment`)
- ✓ Diarios (`account.journal`)
- ✓ Estados de cuenta bancarios

---

## 🚀 Próximos Pasos

### Para Probar:
1. Restaurar backup de QA
2. Verificar que existen stores: `SELECT * FROM res_store;`
3. Ejecutar upgrade a 19.0.0.0
4. Validar resultados con queries del MIGRATION_GUIDE.md

### Para Producción:
1. ⚠️ **BACKUP COMPLETO**
2. Probar en QA primero
3. Revisar logs en QA
4. Configurar parámetros si es necesario
5. Ejecutar en producción
6. Validar resultados

---

## 📝 Notas Importantes

1. **Automático por defecto**: Si no configuras nada, el script detecta automáticamente
2. **Reversible con backup**: Siempre hacer backup antes de ejecutar
3. **Sin pérdida de datos**: Todos los datos se migran o mantienen
4. **Logs detallados**: Buscar "STORE TO BRANCH" en logs

---

## 📚 Archivos Relacionados

- `end-migration.py` - Script principal (modificado)
- `MIGRATION_GUIDE.md` - Guía completa de uso (nuevo)
- `RESUMEN_CAMBIOS.md` - Este archivo (nuevo)

---

**Autor**: GitHub Copilot  
**Fecha**: 2026-04-16  
**Versión**: 19.0.0.0
