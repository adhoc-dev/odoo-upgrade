from openupgradelib import openupgrade


_column_renames = {
    'helpdesk_solution': [
        ('solution_description', 'internal_solution_description'),
    ],
}


_field_renames = [
    ('helpdesk.solution', 'helpdesk_solution', 'solution_description', 'internal_solution_description'),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_columns(env.cr, _column_renames)
    openupgrade.rename_fields(env, _field_renames)
