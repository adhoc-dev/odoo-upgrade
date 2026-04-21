import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

# ============================================================================
# PRE-MIGRATION SCRIPT FOR STORE TO BRANCH MIGRATION
# ============================================================================
#
# Este script hace BACKUP de todas las tablas relacionadas con res.store
# ANTES de que sean deprecadas/eliminadas durante la migración a 19.0
#
# Tablas que se respaldan:
# - res_store: Tabla principal de stores
# - Todos los campos store_id en otras tablas
# - Tablas de relación many2many con res.store
#
# Los backups se crean con sufijo _bu (backup)
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


def column_exists(cr, table_name, column_name):
    """Check if a column exists in a table."""
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        )
    """,
        (table_name, column_name),
    )
    return cr.fetchone()[0]


def backup_res_store_table(cr):
    """Hace backup de la tabla res_store completa."""
    if not table_exists(cr, "res_store"):
        _logger.info("Table res_store does not exist, skipping backup")
        return

    backup_table = "res_store_bu"

    # Eliminar backup anterior si existe
    if table_exists(cr, backup_table):
        _logger.info("Dropping existing backup table: %s", backup_table)
        cr.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(backup_table)))

    # Crear backup
    _logger.info("Creating backup: res_store -> %s", backup_table)
    cr.execute(
        sql.SQL("CREATE TABLE {} AS SELECT * FROM res_store").format(
            sql.Identifier(backup_table)
        )
    )

    # Contar registros
    cr.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(backup_table)))
    count = cr.fetchone()[0]
    _logger.info("✓ Backed up %s records from res_store", count)


def backup_store_id_columns(cr):
    """
    Hace backup de todos los campos store_id en todas las tablas.

    Estrategia:
    - Busca todas las columnas llamadas 'store_id'
    - Agrega columna store_id_bu en cada tabla
    - Copia el valor de store_id a store_id_bu
    """
    # Buscar todas las tablas que tienen columna store_id
    cr.execute(
        """
        SELECT DISTINCT table_name
        FROM information_schema.columns
        WHERE column_name = 'store_id'
          AND table_schema = 'public'
          AND table_name NOT LIKE '%_bu'
        ORDER BY table_name
    """
    )

    tables_with_store_id = [row[0] for row in cr.fetchall()]

    if not tables_with_store_id:
        _logger.info("No tables with store_id column found")
        return

    _logger.info(
        "Found %s tables with store_id column: %s",
        len(tables_with_store_id),
        tables_with_store_id,
    )

    for table in tables_with_store_id:
        # Verificar que la tabla no sea res_store misma (ya tiene backup completo)
        if table == "res_store":
            continue

        backup_column = "store_id_bu"

        # Agregar columna de backup si no existe
        if not column_exists(cr, table, backup_column):
            _logger.info("Adding backup column %s.%s", table, backup_column)
            cr.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN {} INTEGER").format(
                    sql.Identifier(table), sql.Identifier(backup_column)
                )
            )

        # Copiar datos
        _logger.info("Backing up %s.store_id -> %s.%s", table, table, backup_column)
        cr.execute(
            sql.SQL("UPDATE {} SET {} = store_id WHERE store_id IS NOT NULL").format(
                sql.Identifier(table), sql.Identifier(backup_column)
            )
        )

        # Contar registros respaldados
        cr.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE {} IS NOT NULL").format(
                sql.Identifier(table), sql.Identifier(backup_column)
            )
        )
        count = cr.fetchone()[0]
        if count > 0:
            _logger.info("  ✓ Backed up %s records", count)


def backup_many2many_relations(cr):
    """
    Hace backup de tablas de relación many2many que involucran res.store.

    Busca tablas que:
    - Tienen columnas con patrón *_store_id
    - Son tablas de relación (usualmente tienen dos columnas _id)
    """
    # Buscar constraint de foreign key que apuntan a res_store
    cr.execute(
        """
        SELECT DISTINCT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'res_store'
          AND tc.table_name NOT LIKE '%_bu'
        ORDER BY tc.table_name
    """
    )

    m2m_tables = cr.fetchall()

    if not m2m_tables:
        _logger.info("No many2many relations with res.store found")
        return

    _logger.info(
        "Found %s many2many relations with res.store: %s",
        len(m2m_tables),
        [t[0] for t in m2m_tables],
    )

    for table_name, column_name in m2m_tables:
        # Solo respaldar si parece ser tabla de relación (tiene _rel en el nombre)
        if "_rel" not in table_name:
            _logger.info(
                "Skipping %s.%s (not a relation table)", table_name, column_name
            )
            continue

        backup_table = f"{table_name}_bu"

        # Eliminar backup anterior si existe
        if table_exists(cr, backup_table):
            _logger.info("Dropping existing backup table: %s", backup_table)
            cr.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(backup_table)))

        # Crear backup
        _logger.info("Creating backup: %s -> %s", table_name, backup_table)
        cr.execute(
            sql.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
                sql.Identifier(backup_table), sql.Identifier(table_name)
            )
        )

        # Contar registros
        cr.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(backup_table))
        )
        count = cr.fetchone()[0]
        _logger.info("  ✓ Backed up %s records", count)


def backup_store_user_relation(cr):
    """
    Hace backup explícito de la relación many2many entre res.store y res.users
    (campo store_ids en res.users o user_ids en res.store).

    Crea la tabla res_store_user_rel_bu con nombre fijo para que el script
    end-migration pueda leerla de forma confiable, independientemente
    del nombre original de la tabla de relación.
    """
    if not table_exists(cr, "res_store"):
        _logger.info(
            "Table res_store does not exist, skipping store-user relation backup"
        )
        return

    # Buscar tablas que tienen FK a res_store Y a res_users al mismo tiempo
    cr.execute(
        """
        SELECT DISTINCT tc.table_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'res_store'
          AND tc.table_name NOT LIKE '%%_bu'
          AND tc.table_name IN (
              SELECT DISTINCT tc2.table_name
              FROM information_schema.table_constraints AS tc2
              JOIN information_schema.constraint_column_usage AS ccu2
                  ON ccu2.constraint_name = tc2.constraint_name
              WHERE tc2.constraint_type = 'FOREIGN KEY'
                AND ccu2.table_name = 'res_users'
          )
        ORDER BY tc.table_name
        """
    )
    rel_tables = [row[0] for row in cr.fetchall()]

    if not rel_tables:
        _logger.info(
            "No many2many relation table found between res_store and res_users"
        )
        return

    # Usar el primer resultado (normalmente solo hay uno)
    rel_table = rel_tables[0]
    if len(rel_tables) > 1:
        _logger.warning(
            "Found multiple relation tables between res_store and res_users: %s. Using: %s",
            rel_tables,
            rel_table,
        )

    backup_table = "res_store_user_rel_bu"

    if table_exists(cr, backup_table):
        _logger.info("Dropping existing backup table: %s", backup_table)
        cr.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(backup_table)))

    _logger.info(
        "Creating store-user relation backup: %s -> %s", rel_table, backup_table
    )
    cr.execute(
        sql.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
            sql.Identifier(backup_table), sql.Identifier(rel_table)
        )
    )

    cr.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(backup_table)))
    count = cr.fetchone()[0]
    _logger.info("✓ Backed up %s user-store relations (source: %s)", count, rel_table)

    # Loguear las columnas para facilitar el debug
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (backup_table,),
    )
    columns = [row[0] for row in cr.fetchall()]
    _logger.info("  Columns in backup: %s", columns)


def migrate(cr, version):
    """
    Función principal de pre-migración.

    Hace backup de todas las estructuras relacionadas con res.store
    ANTES de que sean deprecadas en Odoo 19.
    """
    _logger.info("=" * 80)
    _logger.info("STARTING PRE-MIGRATION: STORE BACKUP")
    _logger.info("=" * 80)

    # 1. Backup de la tabla res_store completa
    _logger.info("Step 1/4: Backing up res_store table...")
    backup_res_store_table(cr)

    # 2. Backup de todos los campos store_id
    _logger.info("Step 2/4: Backing up store_id columns...")
    backup_store_id_columns(cr)

    # 3. Backup de relaciones many2many genéricas
    _logger.info("Step 3/4: Backing up many2many relations...")
    backup_many2many_relations(cr)

    # 4. Backup explícito de la relación usuarios-stores (store_ids / user_ids)
    _logger.info("Step 4/4: Backing up store-user relation (store_ids)...")
    backup_store_user_relation(cr)

    cr.commit()
