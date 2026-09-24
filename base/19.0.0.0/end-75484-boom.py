def migrate(cr, version):
    """Break in the final phase of the `-u`, and only when the database asks for it.

    The `end-` scripts run after every module is committed in the target version, so a run that
    breaks here cannot be resumed: the next `-u` has to refuse it and say the database has to be
    regenerated. Off unless the database arms it, so it does not get in the way of the main test:

        CREATE TABLE saas_upgrade_test_arm_end ();
    """
    cr.execute("SELECT to_regclass('saas_upgrade_test_arm_end')")
    if not cr.fetchone()[0]:
        return
    raise Exception("Forced failure of task 75484 in the final phase of the -u.")
