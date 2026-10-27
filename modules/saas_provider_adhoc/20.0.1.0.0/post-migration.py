import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)

NPS_TEMPLATES = (
    "nps_16_template_form",
    "nps_template_form",
    "nps_template_included_comments_form",
)


def migrate(cr, version):
    """Change t-esc into t-out in the arch of the NPS survey templates.

    The templates are in a noupdate data file, so the -u keeps the arch of 19.
    The server QWeb of 20 renders t-esc as empty, and the survey sent to the
    clients would come without its question. Only t-esc changes: the rest of the
    arch, edited in the database since 2023, stays as it is, in every language.
    """
    _logger.info("Changing t-esc into t-out in the NPS survey templates")
    cr.execute(
        SQL(
            """
            UPDATE ir_ui_view v
               SET arch_db = (
                       SELECT jsonb_object_agg(lang.key, replace(lang.value, 't-esc=', 't-out='))
                         FROM jsonb_each_text(v.arch_db) lang
                   )
              FROM ir_model_data d
             WHERE d.model = 'ir.ui.view'
               AND d.res_id = v.id
               AND d.module = 'saas_provider_adhoc'
               AND d.name IN %(names)s
               AND v.arch_db::text LIKE %(pattern)s
            """,
            names=NPS_TEMPLATES,
            pattern="%t-esc=%",
        )
    )
    _logger.info("Changed %s NPS survey templates", cr.rowcount)
