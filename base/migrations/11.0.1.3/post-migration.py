# -*- coding: utf-8 -*-
# © 2017 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import json
from psycopg2.extensions import AsIs

from odoo.tools import pickle

from openupgradelib import openupgrade


def map_ir_actions_server_fields(cr):
    """Map model_id from ir_values to ir_actions' binding_model_id. As per
    table inheritance, this will set the values in the related tables such
    as ir_act_server.
    Also set binding_type to action or report depending on the key2
    field of the ir_values entry."""
    cr.execute(
        """
        UPDATE ir_actions ia
        SET binding_model_id = im.id
        FROM ir_values iv, ir_model im
        WHERE iv.value like '%,'||ia.id
            AND iv.model = im.model """)
    cr.execute(
        """
        UPDATE ir_actions ia
        SET binding_type = 'report'
        FROM ir_values iv
        WHERE iv.value like '%,'||ia.id
            AND iv.key2 = 'client_print_multi'""")
    cr.execute(
        """
        UPDATE ir_actions ia
        SET binding_type = 'action'
        WHERE binding_type != 'report' """)


def set_currency_rate_dates(cr):
    """Set currency rate date per company's most popular timezone.
    Rates without a company will be cast to UTC date automatically."""
    cr.execute("SELECT id FROM res_company")
    for company_id, in cr.fetchall():
        cr.execute(
            """
            SELECT rp.tz, count(rp) as cnt
            FROM res_users ru
            JOIN res_partner rp ON ru.partner_id = rp.id
            WHERE ru.company_id = %s
            GROUP BY rp.tz ORDER BY cnt DESC LIMIT 1""",
            (company_id,))
        row = cr.fetchone()
        tz = row[0] if row and row[0] else 'UTC'
        cr.execute(
            """
            UPDATE res_currency_rate
            SET name = (
                %s::TIMESTAMP at TIME ZONE 'UTC'
                AT TIME ZONE %s)::DATE
            WHERE company_id = %s""", (
                AsIs(openupgrade.get_legacy_name('name')),
                tz, company_id))


def merge_default_ir_values(cr):
    """Merge 'default' ir.values records into ir.default records. We only
    consider 'default' ir.values with non empty values. Delete ir.values record
    at the end."""
    cr.execute("""
        SELECT id, create_date, write_date, create_uid, write_uid, user_id,
            company_id, name, model, value
        FROM ir_values WHERE key = 'default' AND value IS NOT NULL;""")
    query = """
        INSERT INTO ir_default (
            create_date, write_date, create_uid, write_uid, user_id,
            company_id, field_id, json_value)
        VALUES %s;
        DELETE FROM ir_values WHERE id = %s;"""
    for r in cr.fetchall():
        cr.execute("""
            SELECT id FROM ir_model_fields WHERE name = %s AND model = %s;
        """, (r[7], r[8]))
        model_field = cr.fetchone()

        if model_field and model_field[0]:
            # taken from odoo 10 to get pickled value and odoo 11 to store JSON
            # value
            value = pickle.loads(bytes(r[9], 'utf-8'))
            json_value = json.dumps(value, ensure_ascii=False)
            values = (r[1], r[2], r[3], r[4], r[5], r[6], model_field[0],
                      json_value)
            cr.execute(query, (values, r[0]))
    return True


def fill_cron_action_server_post(env):
    """As cron now inherits by delegation from server action, we need to create
    manually the server action record for each of the existing crons, and
    translate fields for achieving the same result.
    """
    default_vals = {
        'state': 'code',
        'type': 'ir.actions.server',
        'usage': 'ir_cron',
        'binding_type': 'action',
        'sequence': 10,
    }
    env.cr.execute("""
        SELECT ic.id, ic.create_uid, ic.create_date, ic.write_uid, ic.args,
            ic.write_date, ic.name, im.id AS model_id, ic.function
        FROM ir_cron AS ic,
            ir_model AS im
        WHERE
            im.model = ic.model
     """)
    for act in env.cr.dictfetchall():
        vals = default_vals.copy()
        vals.update({
            'create_uid': act['create_uid'],
            'create_date': act['create_date'],
            'write_uid': act['write_uid'],
            'write_date': act['write_date'],
            'name': act['name'],
            'model_id': act['model_id'],
            'code': 'records.%s%s' % (act['function'], act['args'] or '()'),
        })
        openupgrade.logged_query(
            env.cr, """
            INSERT INTO ir_act_server
              (create_uid, create_date, write_uid, write_date,
               code, state, type, usage, name, model_id,
               binding_type, sequence)
            VALUES (
              %(create_uid)s, %(create_date)s, %(write_uid)s, %(write_date)s,
              %(code)s, %(state)s, %(type)s, %(usage)s, %(name)s, %(model_id)s,
              %(binding_type)s, %(sequence)s
            )
            RETURNING id""", vals,
        )
        server_action_id = env.cr.fetchone()[0]
        # Write in the ir.cron record the parent ir.actions.server ID
        env.cr.execute(
            "UPDATE ir_cron SET ir_actions_server_id = %s WHERE id = %s",
            (server_action_id, act['id']),
        )


@openupgrade.migrate()
def migrate(env, version):
    map_ir_actions_server_fields(env.cr)
    set_currency_rate_dates(env.cr)
    merge_default_ir_values(env.cr)
    fill_cron_action_server_post(env)
    openupgrade.load_data(
        env.cr, 'base', 'migrations/11.0.1.3/noupdate_changes.xml',
    )
