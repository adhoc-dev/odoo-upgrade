import logging
from ast import literal_eval

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

SEARCH_FIELDS_PARAM = "website_sale_search_improved.search_fields"


def _field_path_exists(env, path):
    model = "product.template"
    for name in path.split("."):
        field = env[model]._fields.get(name) if model else None
        if not field:
            return False
        model = field.comodel_name if field.relational else None
    return True


def migrate(cr, version):
    """Clean the extra shop search fields that 20 can not use or already searches.

    website_sale_search_improved adds the field paths of `website_sale_search_improved.search_fields`
    to the shop search. The settings check them only on save, so after the jump to 20 the list
    can keep:

    - paths that do not exist on product.template in 20: every shop search fails with
      "Invalid field";
    - paths that 20 already searches natively (`_get_website_sale_search_fields`, like
      `attribute_line_ids.value_ids.name`): they only duplicate the native search.

    Both are dropped. The description fields stay: 20 searches them only when the website
    searches in descriptions. Goes in end-migration because the fields of a path can come from
    modules that load after this one. No customer note (task 76558).
    """
    _logger.info("Running end-migration for website_sale_search_improved version %s", version)

    env = util.env(cr)
    params = env["ir.config_parameter"].sudo()
    value = params.get_str(SEARCH_FIELDS_PARAM)
    if not value:
        return
    try:
        search_fields = literal_eval(value)
    except (ValueError, SyntaxError):
        _logger.warning("%s is not a list, left as is: %r", SEARCH_FIELDS_PARAM, value)
        return
    if not isinstance(search_fields, list) or not all(isinstance(path, str) for path in search_fields):
        _logger.warning("%s is not a list of field paths, left as is: %r", SEARCH_FIELDS_PARAM, value)
        return

    native = set(env["product.template"]._get_website_sale_search_fields(search_in_description=False))
    missing = [path for path in search_fields if not _field_path_exists(env, path)]
    redundant = [path for path in search_fields if path in native and path not in missing]
    if not missing and not redundant:
        return

    kept = [path for path in search_fields if path not in missing and path not in redundant]
    params.set_str(SEARCH_FIELDS_PARAM, str(kept))
    _logger.info(
        "%s: dropped fields missing in 20 %s and fields 20 searches natively %s, kept %s",
        SEARCH_FIELDS_PARAM,
        missing,
        redundant,
        kept,
    )
