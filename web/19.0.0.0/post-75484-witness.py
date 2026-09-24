def migrate(cr, version):
    """Leave a row every time this script runs: a module that already passed must not run it twice."""
    cr.execute("""
        CREATE TABLE IF NOT EXISTS saas_upgrade_test_witness (
            id serial PRIMARY KEY,
            module varchar,
            ran_at timestamp DEFAULT (now() at time zone 'UTC'))
    """)
    cr.execute("INSERT INTO saas_upgrade_test_witness (module) VALUES (%s)", ("web",))
