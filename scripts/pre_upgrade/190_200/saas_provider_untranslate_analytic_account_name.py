import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Make account.analytic.account.name not translatable, as saas_provider declares in 20.

    The team renames accounts in es_419, so es_419 goes to en_US first where they
    differ: the column keeps only en_US when it stops being translatable.

    It has to run before the -u. The -u reads the translated fields from
    ir_model_fields when it starts, and keeps them translated while it loads:
    the column would stay jsonb and the ORM would read the name as a dict.
    Once ir_model_fields says it is not translated, the -u converts the column.
    """
    if not util.module_installed(cr, "saas_provider"):
        return
    if util.column_type(cr, "account_analytic_account", "name") != "jsonb":
        return

    cr.execute(
        """
        UPDATE account_analytic_account
           SET name = jsonb_set(name, '{en_US}', name->'es_419')
         WHERE name->>'es_419' <> ''
           AND name->>'es_419' IS DISTINCT FROM name->>'en_US'
        """
    )
    _logger.info("Copied the es_419 name to en_US on %s analytic accounts", cr.rowcount)
    cr.execute(
        """
        UPDATE ir_model_fields
           SET translate = NULL
         WHERE model = 'account.analytic.account'
           AND name = 'name'
        """
    )
