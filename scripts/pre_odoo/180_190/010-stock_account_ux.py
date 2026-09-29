BACKUP_TABLE = "stock_move_account_move_id_bu"


def migrate(cr, version):
    cr.execute("SELECT 1 FROM ir_module_module WHERE name = 'stock_account' AND state = 'installed'")
    if not cr.fetchone():
        return

    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT DISTINCT ON (svl.stock_move_id)
                   svl.stock_move_id AS stock_move_id,
                   svl.account_move_id AS account_move_id
              FROM stock_valuation_layer svl
              JOIN account_move am ON am.id = svl.account_move_id
             WHERE svl.account_move_id IS NOT NULL
               AND svl.stock_move_id IS NOT NULL
               AND am.state = 'posted'
             ORDER BY svl.stock_move_id, svl.id
        """
        % BACKUP_TABLE
    )
    # Sin PK, el test_ensure_has_pk de Odoo la marca CRITICAL en cada corrida. El DISTINCT ON
    # ya garantiza un solo registro por stock_move_id y el WHERE descarta los NULL.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (stock_move_id)" % BACKUP_TABLE)
