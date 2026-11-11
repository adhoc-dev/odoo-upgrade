import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/base/0.0.0/end-230-followup_levels.py, on the other side of the upgrade.
BACKUP_TABLE = "account_followup_followup_line_bu"
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20
# Same window as KPI 558: a level counts as used if a journal item of that date has it.
USED_DAYS = 180


def migrate(cr, version):
    """Back up the follow-up levels, with what 20.0 drops from them, before the database is sent to Odoo.

    In 20.0 a level loses name, auto_execute, join_invoices and additional_follower_ids:
    the automatic sending moves to a switch per company. The consumer needs them to decide,
    company by company, whether to turn the switch on and which manual levels become
    activities, and to tell the customer what changed.

    A level is used if a journal item dated in the last USED_DAYS days has it. In 19.0 the
    journal item does not keep when the level was applied, so its date is the best guess.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if not should_back_up(cr, BACKUP_TABLE, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=["account_followup"]):
        return

    cr.execute("SELECT to_regclass('account_followup_followup_line_res_users_rel') IS NOT NULL")
    followers = (
        """
        (SELECT count(*)
           FROM account_followup_followup_line_res_users_rel r
          WHERE r.account_followup_followup_line_id = l.id)
        """
        if cr.fetchone()[0]
        else "0"
    )

    _logger.info("Backing up the follow-up levels into %s", BACKUP_TABLE)
    count = create_backup(
        cr,
        BACKUP_TABLE,
        """
        WITH used AS (
            SELECT DISTINCT followup_line_id AS id
              FROM account_move_line
             WHERE followup_line_id IS NOT NULL
               AND date >= CURRENT_DATE - %%s
        )
        SELECT l.id,
               l.company_id,
               COALESCE(
                   l.name ->> p.lang,
                   l.name ->> 'en_US',
                   (SELECT value FROM jsonb_each_text(l.name) LIMIT 1)
               ) AS name,
               l.delay,
               COALESCE(l.auto_execute, false) AS auto_execute,
               COALESCE(l.send_email, false) AS send_email,
               COALESCE(l.send_sms, false) AS send_sms,
               COALESCE(l.create_activity, false) AS create_activity,
               l.mail_template_id,
               l.sms_template_id,
               COALESCE(l.join_invoices, false) AS join_invoices,
               %s AS followers,
               used.id IS NOT NULL AS used
          FROM account_followup_followup_line l
          JOIN res_company c ON c.id = l.company_id
     LEFT JOIN res_partner p ON p.id = c.partner_id
     LEFT JOIN used ON used.id = l.id
        """
        % followers,
        (USED_DAYS,),
    )
    _logger.info("Backed up %s follow-up levels", count)
