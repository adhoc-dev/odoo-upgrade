import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove the shared postgres from saas_provider.

    In 20 every k8s environment runs on CNPG, so the postgres servers, the
    environment servers, the database server and the postgres mode go away, with
    their history. The code asks for the environment type instead of the mode.
    The tunnel parameter only served the shared postgres, and remove_model keeps it.
    """
    _logger.info("Running pre-migration of saas_provider for version %s", version)

    util.remove_field(cr, "saas.database", "environment_postgres_mode")
    util.remove_field(cr, "saas.environment", "postgres_mode")
    util.remove_record(cr, "saas_provider.ir_cron_remove_hanging_databases")
    util.remove_field(cr, "saas.database", "postgres_server_id")
    util.remove_field(cr, "saas.environment", "postgres_server_ids")
    util.remove_model(cr, "saas.environment.postgres.server")
    util.remove_model(cr, "saas.postgres.server")
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", ["saas_postgres_server.use_tunnel"])
