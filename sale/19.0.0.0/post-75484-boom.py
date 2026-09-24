def migrate(cr, version):
    """Break the `-u` halfway, until the database says it can pass.

    `sale` is in the middle of the graph: the run leaves the modules before it committed in the
    target version, and the ones after it untouched. Disarm it from the client database,
    without touching this repo, and send the `-u` again:

        CREATE TABLE saas_upgrade_test_disarm ();
    """
    cr.execute("""
        CREATE TABLE IF NOT EXISTS saas_upgrade_test_witness (
            id serial PRIMARY KEY,
            module varchar,
            ran_at timestamp DEFAULT (now() at time zone 'UTC'))
    """)
    cr.execute("INSERT INTO saas_upgrade_test_witness (module) VALUES (%s)", ("sale",))

    cr.execute("SELECT to_regclass('saas_upgrade_test_disarm')")
    if cr.fetchone()[0]:
        return
    raise Exception(
        "Forced failure of task 75484. To let this module pass, run on this database: "
        "CREATE TABLE saas_upgrade_test_disarm ();"
    )
