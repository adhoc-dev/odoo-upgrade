import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Reload the code of the "Plan cluster migration" server action.

    The action is in a noupdate data file, so the -u keeps the code of 19. That
    code called _(), which is not in the evaluation context of server actions, and
    in 20 the logic moved to saas.database.action_schedule_cluster_migration.
    Only the code is reloaded: the rest of the record, its name included, stays
    as the database has it.
    """
    _logger.info("Reloading the code of saas_k8s.action_server_schedule_migrate")
    util.update_record_from_xml(
        cr, "saas_k8s.action_server_schedule_migrate", fields={"code"}
    )
