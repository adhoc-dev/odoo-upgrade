# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# TODO borrar o implementar
# def update_model_terms_translations(env):
#     """ Adapt to changes in https://github.com/odoo/odoo/pull/26925, that
#     introduces a separate translation type for xml structured fields. First,
#     deduplicate existing model translations with new model_terms translations
#     that were loaded during the migration. """
#     openupgrade.logged_query(
#         env.cr, """ DELETE FROM ir_translation WHERE id IN (
#         SELECT it2.id FROM ir_translation it1
#         JOIN ir_translation it2 ON it1.type in ('model', 'model_terms')
#             AND it2.type in ('model', 'model_terms')
#             AND it1.name = it2.name
#             AND it1.res_id = it2.res_id
#             AND it1.lang = it2.lang
#             AND it1.id < it2.id); """)
#     names = []
#     for rec in env['ir.model.fields'].search([('translate', '=', True)]):
#         try:
#             field = env[rec.model]._fields[rec.name]
#         except KeyError:
#             continue
#         if callable(field.translate):
#             names.append('%s,%s' % (rec.model, rec.name))
#     if names:
#         openupgrade.logged_query(
#             env.cr,
#             """ UPDATE ir_translation
#             SET type = 'model_terms'
#             WHERE type = 'model' AND name IN %s """,
#             (tuple(names),))

@openupgrade.migrate()
def migrate(env, version):
    # lo hacemos con try porque en pocos casos nos dio error y no queremos
    # bloquear upgrade por esto
    try:
        openupgrade.disable_invalid_filters(env)
    except:
        pass
    env.cr.execute(
        "UPDATE ir_module_module SET latest_version = '12.0.1.3' "
        "WHERE name = 'base'")
    # recargamos traducciones (nos da error y ademas seguramente no es necesario)
    # env['base.language.install'].create({'lang': 'es_AR', 'overwrite': True}).lang_install()
