import logging

from odoo.tools import SQL

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Running 'complete_model_in_export_templates.py' script for version %s", version)
    cr.execute(
        SQL(
            """
            SELECT attname
            FROM pg_attribute
            WHERE attrelid = (
                SELECT oid
                FROM pg_class
                WHERE relname = 'ir_exports'
            )
            AND attname = 'model_id';
            """
        )
    )
    has_model_id_column = cr.fetchall()
    if has_model_id_column:
        cr.execute(
            SQL("SELECT id, resource FROM ir_exports WHERE model_id is NULL;")
        )
        recs = cr.fetchall()
        for id, resource in recs:
            if resource == "_unknown":
                continue
            cr.execute(
                SQL(
                    "SELECT id FROM ir_model WHERE model = %(resource)s;",
                    resource=resource
                )
            )
            model = cr.fetchall()
            if model:
                model_id = model[0][0]  # fetchall() returns list of tuples
                cr.execute(
                    SQL(
                        "UPDATE ir_exports SET model_id = %(model_id)s WHERE id = %(id)s;",
                        model_id=model_id,
                        id=id
                    )
                )
