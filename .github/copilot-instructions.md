# Instrucciones para GitHub Copilot - Repositorio de Upgrades

## Contexto del Repositorio

Este repositorio contiene scripts de migración para módulos de Odoo. Los scripts se utilizan para actualizar bases de datos de versiones anteriores de Odoo a versiones más recientes, manejando cambios en la estructura de datos, modelos, campos y configuraciones.

## Estructura de Directorios de Upgrade

### Repositorio de Upgrades: `odoo-upgrade`
- Estructura: `modules/nombre_modulo/version/script-tipo.py`
- Ejemplo: `modules/l10n_ar_withholding/17.0.0.0/pre-migration.py`
- `modules/` es lo que Odoo lee como `--upgrade-path` (solo módulos); `scripts/pre_odoo/` y `scripts/pre_upgrade/` son nuestras fases; `lib/oba/` los helpers (`from oba import ...`, con `lib/` en el `PYTHONPATH`); `tests/` la siembra y el check declarativo
- Versiones siguen formato: `X.Y.Z.W` (ej: `15.0.0.0`, `17.0.0.0`, `18.0.0.0`)

### Tipos de Scripts de Migración

#### 1. **pre-migration.py** (Pre-upgrade)
- **Cuándo se ejecuta**: ANTES de que Odoo cargue los módulos actualizados
- **Propósito principal**: 
  - Preparar la base de datos para los cambios
  - Hacer backup de columnas que serán eliminadas
  - Renombrar campos, tablas o modelos
  - Deshabilitar constraints que causarían errores
  - Monkey patches temporales

**Ejemplo típico:**
```python
from odoo.upgrade import util


def migrate(cr, version):
    # Backup de una columna antes de que se elimine
    util.create_column(
        cr, "account_payment", "tax_withholding_id_bu",
        util.column_type(cr, "account_payment", "tax_withholding_id"),
    )
    cr.execute("UPDATE account_payment SET tax_withholding_id_bu = tax_withholding_id")

    # util.rename_field(cr, 'account.payment', 'old_field', 'new_field')
```

#### 2. **post-migration.py** (Post-upgrade)
- **Cuándo se ejecuta**: DESPUÉS de que Odoo carga los módulos, pero antes del end-migration
- **Propósito principal**:
  - Migrar datos de campos/tablas antiguas a nuevas
  - Actualizar configuraciones
  - Ejecutar lógica de negocio específica de la migración

**Ejemplo típico:**
```python
from odoo.upgrade import util

def migrate_taxes_config(env):
    query = """UPDATE account_tax SET
        type_tax_use = 'none',
        l10n_ar_withholding_payment_type = type_tax_use
    WHERE type_tax_use IN ('customer', 'supplier')"""
    cr.execute(query)

def migrate(cr, version):
    env = util.env(cr)
    migrate_taxes_config(env)
```

#### 3. **end-migration.py** (End-upgrade)
- **Cuándo se ejecuta**: AL FINAL del proceso de upgrade
- **Propósito principal**:
  - Cargar datos finales
  - Limpiezas finales
  - Activar configuraciones

#### 4. Scripts Especiales
- **pre-0-*.py**: Scripts que se ejecutan antes que el script principal pre-migration
- **post-0-*.py**: Scripts adicionales post-migration
- **pre-fix-*.py**, **post-fix-*.py**: Scripts específicos para arreglar problemas

## Librerías y Funciones Disponibles

### **REGLA ADHOC: solo `odoo.upgrade.util`**

**REGLA PRINCIPAL**: Los scripts usan `from odoo.upgrade import util`. Desde la 20 no se usa `openupgradelib`, tampoco para `copy_columns`. Solo queda en scripts de saltos hasta la 19 que ya la usan.

### 1. **odoo.upgrade.util** (Librería PREFERIDA)
```python
from odoo.upgrade import util
```

**ESTA ES LA LIBRERÍA PRINCIPAL QUE DEBEMOS USAR**

**Categorías principales:**

#### Operaciones de Módulos:
- `util.module_installed(cr, module)`: Verificar si módulo está instalado
- `util.rename_module(cr, old, new)`: Renombrar módulo ⭐ **PREFERIR sobre openupgrade**
- `util.merge_module(cr, old, into)`: Fusionar módulos ⭐ **PREFERIR sobre openupgrade**
- `util.remove_module(cr, module)`: Eliminar módulo completamente
- `util.force_install_module(cr, module)`: Forzar instalación

#### Operaciones de Modelos:
- `util.rename_model(cr, old, new)`: Renombrar modelo ⭐ **PREFERIR sobre openupgrade**
- `util.remove_model(cr, model)`: Eliminar modelo
- `util.merge_model(cr, source, target)`: Fusionar modelos

#### Operaciones de Campos:
- `util.rename_field(cr, model, old, new)`: Renombrar campo ⭐ **PREFERIR sobre openupgrade**
- `util.remove_field(cr, model, field)`: Eliminar campo
- `util.convert_m2o_field_to_m2m(cr, model, field)`: Convertir Many2one a Many2many
- `util.change_field_selection_values(cr, model, field, mapping)`: Cambiar valores de selección

#### Operaciones de Registros:
- `util.remove_view(cr, xml_id)`: Eliminar vista
- `util.remove_record(cr, xml_id)`: Eliminar registro
- `util.rename_xmlid(cr, old, new)`: Renombrar XML ID ⭐ **PREFERIR sobre openupgrade**
- `util.update_record_from_xml(cr, xml_id)`: Actualizar desde XML

#### ORM y Performance:
- `util.env(cr)`: Crear environment
- `util.recompute_fields(cr, model, fields, ids)`: Recomputar campos
- `util.iter_browse(model, ids)`: Iterar sobre recordsets grandes

#### SQL y Base de Datos:
- `util.parallel_execute(cr, queries)`: Ejecutar queries en paralelo ⭐ **PREFERIR sobre openupgrade.logged_query**
- `util.explode_execute(cr, query, table)`: Ejecutar query dividida en chunks
- `util.column_exists(cr, table, column)`: Verificar si columna existe
- `util.create_column(cr, table, column, definition)`: Crear columna
- `util.rename_table(cr, old_table, new_table)`: Renombrar tabla ⭐ **PREFERIR sobre openupgrade**

### 2. **openupgradelib** (No se usa en scripts nuevos)

Un script nuevo no importa `openupgradelib`. Si un PR la usa, sugerir el equivalente en `util`:
- ❌ `openupgrade.copy_columns()` → ✅ `util.create_column(cr, table, column_bu, util.column_type(cr, table, column))` + `UPDATE table SET column_bu = column`
- ❌ `openupgrade.rename_fields()` → ✅ `util.rename_field()`
- ❌ `openupgrade.rename_models()` → ✅ `util.rename_model()`
- ❌ `openupgrade.rename_tables()` → ✅ `util.rename_table()`
- ❌ `openupgrade.rename_xmlids()` → ✅ `util.rename_xmlid()`
- ❌ `openupgrade.logged_query()` → ✅ `cr.execute()` o `util.parallel_execute()`

### 3. Patrones Comunes de Datos

#### Estructuras de Datos Típicas:
```python
# Para rename_fields
_field_renames = [
    ('model.name', 'table_name', 'old_field', 'new_field'),
]

# Para rename_tables
_table_renames = [
    ('old_table', 'new_table'),
]

# Para rename_xmlids
_xmlid_renames = [
    ('module.old_xmlid', 'module.new_xmlid'),
]
```

## Mejores Prácticas para Review de PRs

### 1. **Validar Estructura del Script**
- ✅ Verificar que tenga la función `migrate(cr, version)` (NO usar `@openupgrade.migrate()`)
- ✅ Confirmar imports correctos (preferir `from odoo.upgrade import util`)
- ✅ Validar que el tipo de script (pre/post/end) es apropiado para las operaciones
- ✅ **IMPORTANTE**: Pedir reemplazar openupgradelib por util

### 2. **Operaciones Pre-migration**
- ✅ Verificar backups de columnas antes de eliminarlas
- ✅ Confirmar que los renames de campos/tablas/modelos son correctos
- ✅ Validar que se deshabiliten constraints problemáticos
- ❌ Validar que NO se utilice el ORM

### 3. **Operaciones Post-migration**
- ✅ Verificar migración de datos de campos backup
- ✅ Confirmar queries SQL para actualización de datos
- ✅ Validar lógica de negocio específica
- ✅ **PREFERIR**: `cr.execute()` o `util.parallel_execute()` sobre `openupgrade.logged_query()`

### 4. **Seguridad y Performance**
- ✅ Usar `util.parallel_execute()` para múltiples queries
- ✅ Usar `util.explode_execute()` para queries grandes
- ✅ Verificar que no hay queries que puedan causar locks prolongados
- ✅ Confirmar uso de transacciones apropiadas

### 5. **Gestión de Versiones**
- ✅ Verificar que el directorio de versión es correcto (ej: `17.0.0.0`)
- ✅ Confirmar que el script aplica a la versión correcta
- ✅ Validar compatibilidad con versiones múltiples si aplica

### 6. **Manejo de Errores**
- ✅ Verificar uso de try/catch donde sea apropiado
- ✅ Confirmar logging adecuado con `_logger`
- ✅ Validar que existan verificaciones antes de operaciones riesgosas

### 7. **Naming Conventions**
- ✅ Campos backup terminan en `_bu` (ej: `field_name_bu`)
- ✅ Tablas backup terminan en `_bu` (ej: `table_name_bu`)
- ✅ Scripts siguen patrón: `pre-migration.py`, `post-migration.py`, `end-migration.py`

## Ejemplos de Errores Comunes a Detectar

### ❌ **Error: Usar decorador @openupgrade.migrate()**
```python
# MALO - No usar este decorador
@openupgrade.migrate()
def migrate(env, version):  # ❌ Firma incorrecta también
    pass
```

### ✅ **Correcto: Función migrate simple**
```python
# BUENO - Función simple con firma correcta
def migrate(cr, version):  # ✅ Firma correcta: (cr, version)
    pass
```

### ❌ **Error: Usar openupgradelib cuando util está disponible**
```python
# MALO - Usar openupgrade cuando util puede hacerlo
from openupgradelib import openupgrade

def migrate(cr, version):
    openupgrade.rename_fields(env, [...])  # ❌ util.rename_field() es mejor
```

### ✅ **Correcto: Usar solo util**
```python
# BUENO - Solo util
from odoo.upgrade import util

def migrate(cr, version):
    util.rename_field(cr, 'model.name', 'old', 'new')  # ✅
```

### ❌ **Error: Usar ORM en pre-migration**
```python
# MALO - No hacer en pre-migration
def migrate(cr, version):
    env = util.env(cr)
    records = env['account.payment'].search([])  # ❌ ORM no disponible en pre
```

### ✅ **Correcto: Usar SQL directo en pre-migration**
```python
# BUENO - Usar SQL en pre-migration
def migrate(cr, version):
    cr.execute("UPDATE account_payment SET ...")  # ✅
```

## REGLAS ESPECÍFICAS ADHOC - CRÍTICAS PARA REVIEW

### 🚨 **PREFERENCIAS OBLIGATORIAS DE ADHOC:**

1. **Librería**: `from odoo.upgrade import util` (NO openupgradelib, tampoco para copy_columns)
2. **Función migrate**: `def migrate(cr, version):` (NO usar @openupgrade.migrate())
3. **Pedir** reemplazar openupgradelib por util en todo script nuevo

### 🔍 **CHECKLIST DE REVIEW PRIORITARIO:**

#### Al revisar un PR, SIEMPRE verificar:
- ❌ ¿Usa `@openupgrade.migrate()`? → Sugerir eliminarlo
- ❌ ¿La función es `migrate(env, version)`? → Cambiar a `migrate(cr, version)`
- ❌ ¿Usa `openupgrade.rename_*()` o similar? → Sugerir equivalente en `util`
- ❌ ¿Usa `openupgrade.logged_query()`? → Sugerir `cr.execute()` o `util.parallel_execute()`
- ❌ ¿Usa `openupgrade.copy_columns()`? → Sugerir `util.create_column()` + `UPDATE`

#### SUGERENCIAS AUTOMÁTICAS:
```python
# Si ves esto:
openupgrade.rename_fields(env, [...])
# Sugerir esto:
util.rename_field(cr, 'model', 'old', 'new')

# Si ves esto:
openupgrade.logged_query(cr, "UPDATE ...")
# Sugerir esto:  
cr.execute("UPDATE ...")
```

## Referencias Adicionales

- **Odoo Upgrade Utils**: https://github.com/odoo/upgrade-util
- **Documentación Oficial**: https://www.odoo.com/documentation/master/developer/reference/upgrades/upgrade_scripts.html

---

⚠️ **IMPORTANTE**: Estas reglas son específicas de ADHOC. Al hacer review, pide `util` en lugar de `openupgradelib` y la estructura de función correcta `migrate(cr, version)` sin decoradores.
