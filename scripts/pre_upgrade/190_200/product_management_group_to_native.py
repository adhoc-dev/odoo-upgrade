import logging

from odoo.tools import SQL
from odoo.upgrade import util

from oba import log_message, timed

_logger = logging.getLogger(__name__)

MODULE = "product_management_group"
MODULE_GROUP = "product_management_group.group_products_management"
NATIVE_GROUP = "product.group_product_manager"


@timed
def migrate(cr, version):
    """Move the bases from product_management_group to the native Product / Create group.

    In 20 the module stays as an extra, not supported. The users of its group get the
    native group, which also lets them manage pricelists, units, categories and attributes,
    and the module is removed. It goes before the -u, so the -u never loads the module.

    The upgrade line 2115 does the same on the jump to 19, without the removal.
    """
    if not util.module_installed(cr, MODULE):
        return

    dependents = installed_dependents(cr)
    if dependents:
        log_message(
            cr,
            "No se desinstaló %s porque lo usan %s: hay que decidir si esos módulos siguen "
            "dependiendo de él o pasan al permiso nativo Productos / Crear." % (MODULE, dependents),
            "warning",
            module=MODULE,
        )
        return

    module_group_id = util.ref(cr, MODULE_GROUP)
    native_group_id = util.ref(cr, NATIVE_GROUP)
    if module_group_id and native_group_id:
        # Only internal users: the native group implies base.group_user.
        cr.execute(
            SQL(
                """
                INSERT INTO res_groups_users_rel (gid, uid)
                     SELECT %s, r.uid
                       FROM res_groups_users_rel r
                       JOIN res_users u ON u.id = r.uid
                      WHERE r.gid = %s
                        AND NOT u.share
                ON CONFLICT DO NOTHING
                """,
                native_group_id,
                module_group_id,
            )
        )
        _logger.info("Gave %s to %s users of %s", NATIVE_GROUP, cr.rowcount, MODULE_GROUP)

    util.remove_module(cr, MODULE)
    _logger.info("Removed %s", MODULE)


def installed_dependents(cr):
    cr.execute(
        """
        SELECT m.name
          FROM ir_module_module m
          JOIN ir_module_module_dependency d ON d.module_id = m.id
         WHERE d.name = %s
           AND m.state NOT IN ('uninstalled', 'uninstallable')
      ORDER BY m.name
        """,
        (MODULE,),
    )
    return [name for (name,) in cr.fetchall()]
