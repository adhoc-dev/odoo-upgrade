# Copyright 2019 Tecnativa - Ernesto Tejeda
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # el post lo hacemos desde un upgrade line, esto es para evitar que tarde mucho el computo
    query = "ALTER TABLE account_move ADD sale_type_id VARCHAR"
    openupgrade.logged_query(env.cr, query, [])
