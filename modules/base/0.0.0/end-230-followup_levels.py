"""Carry the follow-up levels of 19.0 over to the automatic reminders of 20.0.

Reads what scripts/pre_odoo/190_200/030-backup_followup_levels.py backed up on the old
database, and applies the rule the PO decided (spec script-seguimiento-de-cobranza-en-20
of actua-20):

1. A company that used an automatic level in the last 180 days gets the switch on. Its
   manual levels that sent a mail or an SMS only schedule an activity that says what to
   send, so nothing a person sends today starts going out by itself.
2. A branch that was reminded with the levels of its parent gets a copy of them, the
   switch of the parent, and its open items on the copied level: in 20.0 a company only
   uses its own levels.
3. An open invoice with a level and without last_auto_reminder gets due date + days of
   the level: without it the cron of 20.0 never moves it to the next level.
4. The customer notes (upgrade lines 2655 and 2683) get what changed, base by base.

In ``modules/base/0.0.0`` so it runs with every module loaded. Everything the customer note
shows comes from the backup, so a second run emits the same and changes nothing.
"""

import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import add_customer_note, log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "account_followup_followup_line_bu"
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20
MODULE = "account_followup"
DEFAULT_LANG = "es_419"


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=[MODULE]):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        # Not "no levels": nobody looked. Emitting empty keys would tell the customer that
        # nothing changed.
        log_message(
            cr,
            "No existe %s: no se migraron los niveles de seguimiento" % BACKUP_TABLE,
            "warning",
            module="account_followup",
        )
        return

    env = util.env(cr)
    levels = _read_backup(cr)
    companies = _companies(env, levels)
    automatic = {company_id for company_id, info in companies.items() if info["group"] == "automatic"}

    for company_id in sorted(automatic):
        _turn_on(env, company_id, [level for level in levels if level["company_id"] == company_id])
    branches = _copy_to_branches(env, cr, companies)
    _set_last_auto_reminder(cr)
    _activate_cron(env)
    _emit(env, cr, levels, companies, branches)


def _read_backup(cr):
    """The backed up levels that still exist after the pass, with what 20.0 dropped from them."""
    cr.execute(
        SQL(
            """
            SELECT bu.id, bu.company_id, bu.name, bu.delay, bu.auto_execute, bu.send_email,
                   bu.send_sms, bu.create_activity, bu.mail_template_id, bu.sms_template_id,
                   bu.join_invoices, bu.followers, bu.used
              FROM %s bu
              JOIN account_followup_followup_line l ON l.id = bu.id
          ORDER BY bu.company_id, bu.delay
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    names = [column.name for column in cr.description]
    return [dict(zip(names, row)) for row in cr.fetchall()]


def _companies(env, levels):
    """Each company with levels in 19.0, its group for the customer note and its language."""
    companies = {}
    for level in levels:
        info = companies.setdefault(
            level["company_id"], {"used": False, "used_automatic": False, "had_automatic": False}
        )
        info["used"] |= level["used"]
        info["used_automatic"] |= level["used"] and level["auto_execute"]
        info["had_automatic"] |= level["auto_execute"]
    for company_id, info in companies.items():
        company = env["res.company"].browse(company_id)
        info["name"] = company.name
        info["lang"] = company.partner_id.lang or DEFAULT_LANG
        info["group"] = "automatic" if info["used_automatic"] else "manual" if info["used"] else "unused"
    return companies


def _to_activity(level):
    """Whether the rule turns this level into an activity, from what it was in 19.0."""
    return not level["auto_execute"] and (level["send_email"] or level["send_sms"])


def _turn_on(env, company_id, levels):
    """Turn the switch on and the manual levels that sent something into activities."""
    try:
        with env.cr.savepoint():
            company = env["res.company"].browse(company_id)
            if not company.automatic_invoice_reminder:
                company.automatic_invoice_reminder = True
            todo = env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            lang = company.partner_id.lang or DEFAULT_LANG
            for level in levels:
                record = env["account_followup.followup.line"].browse(level["id"])
                # The current state, not the backup: a second run finds nothing to send.
                if not _to_activity(level) or not (record.send_email or record.send_sms):
                    continue
                what = _what_to_send(record, lang)
                record.write(
                    {
                        "send_email": False,
                        "send_sms": False,
                        "create_activity": True,
                        "activity_summary": record.activity_summary or level["name"],
                        "activity_note": "\n".join(filter(None, [record.activity_note, what])),
                        "activity_type_id": record.activity_type_id.id or (todo and todo.id),
                    }
                )
            _logger.info("Turned on the automatic reminders of company %s", company_id)
    except Exception as exc:
        env.invalidate_all()
        log_message(
            env.cr,
            "No se pudieron prender los recordatorios automáticos de la compañía %s: %s" % (company_id, exc),
            "warning",
            module="account_followup",
        )


def _what_to_send(level, lang):
    """The lines of the activity note that say what the person has to send."""
    lines = []
    if level.send_email:
        template = level.mail_template_id.with_context(lang=lang)
        lines.append(
            "Mandar el mail «%s» (asunto: %s)." % (template.name, template.subject)
            if template
            else "Mandar el mail del recordatorio."
        )
    if level.send_sms:
        template = level.sms_template_id.with_context(lang=lang)
        lines.append("Mandar el SMS «%s»." % template.name if template else "Mandar el SMS del recordatorio.")
    return "\n".join(lines)


def _copy_to_branches(env, cr, companies):
    """Give each branch reminded with the levels of a parent a copy of them.

    A branch counts if it had no levels of its own in 19.0 and either has open items on a
    level of a parent (first run) or has levels now (an earlier run copied them). The source
    is the parent whose levels its items have, or the closest one with levels.

    :returns: {branch id: source company id}
    """
    cr.execute(
        """
        SELECT aml.company_id, fl.company_id, count(*)
          FROM account_move_line aml
          JOIN account_followup_followup_line fl ON fl.id = aml.followup_line_id
          JOIN res_company branch ON branch.id = aml.company_id
          JOIN res_company source ON source.id = fl.company_id
         WHERE aml.followup_line_id IS NOT NULL
           AND fl.company_id <> aml.company_id
           AND branch.parent_path LIKE source.parent_path || '%'
      GROUP BY aml.company_id, fl.company_id
      ORDER BY aml.company_id, count(*) DESC
        """
    )
    sources = {}
    for branch_id, source_id, _count in cr.fetchall():
        sources.setdefault(branch_id, source_id)

    cr.execute(
        """
        SELECT DISTINCT l.company_id
          FROM account_followup_followup_line l
          JOIN res_company c ON c.id = l.company_id
         WHERE c.parent_id IS NOT NULL
        """
    )
    for (branch_id,) in cr.fetchall():
        if branch_id in companies or branch_id in sources:
            continue
        # Copied by an earlier run: the closest parent with levels in 19.0 was the source.
        parents = env["res.company"].browse(branch_id).parent_ids[::-1][1:]
        source = next((parent for parent in parents if parent.id in companies), None)
        if source:
            sources[branch_id] = source.id

    branches = {}
    for branch_id, source_id in sorted(sources.items()):
        if branch_id in companies or source_id not in companies:
            # It had levels of its own in 19.0, or the source has none backed up.
            continue
        try:
            with cr.savepoint():
                _copy_levels(env, branch_id, source_id)
            branches[branch_id] = source_id
        except Exception as exc:
            env.invalidate_all()
            log_message(
                cr,
                "No se pudieron copiar los niveles de seguimiento de la compañía %s a la sucursal %s: %s"
                % (source_id, branch_id, exc),
                "warning",
                module="account_followup",
            )
    return branches


def _copy_levels(env, branch_id, source_id):
    Level = env["account_followup.followup.line"]
    branch = env["res.company"].browse(branch_id)
    source = env["res.company"].browse(source_id)
    if not Level.search_count([("company_id", "=", branch_id)], limit=1):
        Level.create(
            [
                {
                    "company_id": branch_id,
                    "delay": level.delay,
                    "mail_template_id": level.mail_template_id.id,
                    "send_email": level.send_email,
                    "sms_template_id": level.sms_template_id.id,
                    "send_sms": level.send_sms,
                    "create_activity": level.create_activity,
                    "activity_summary": level.activity_summary,
                    "activity_note": level.activity_note,
                    "activity_type_id": level.activity_type_id.id,
                    "activity_default_responsible_type": level.activity_default_responsible_type,
                }
                for level in Level.search([("company_id", "=", source_id)])
            ]
        )
        _logger.info("Copied the follow-up levels of company %s to branch %s", source_id, branch_id)
    if branch.automatic_invoice_reminder != source.automatic_invoice_reminder:
        branch.automatic_invoice_reminder = source.automatic_invoice_reminder
    Level.flush_model()
    env.cr.execute(
        """
        UPDATE account_move_line aml
           SET followup_line_id = copy.id
          FROM account_followup_followup_line level
          JOIN account_followup_followup_line copy
            ON copy.company_id = %(branch)s AND copy.delay = level.delay
         WHERE aml.followup_line_id = level.id
           AND level.company_id = %(source)s
           AND aml.company_id = %(branch)s
           AND aml.reconciled IS NOT TRUE
        """,
        {"branch": branch_id, "source": source_id},
    )
    _logger.info("Moved %s open items of branch %s to the copied levels", env.cr.rowcount, branch_id)


def _set_last_auto_reminder(cr):
    """Unblock the open invoices with a level: due date + days of the level.

    The cron of 20.0 moves an item to the next level only if its invoice has
    last_auto_reminder. With installments, the lowest one, so that no installment waits
    longer than it should. A value already there stays.
    """
    cr.execute(
        """
        UPDATE account_move move
           SET last_auto_reminder = due.reminder
          FROM (
                SELECT aml.move_id, min(aml.date_maturity + level.delay) AS reminder
                  FROM account_move_line aml
                  JOIN account_followup_followup_line level
                    ON level.id = aml.followup_line_id AND level.company_id = aml.company_id
                 WHERE aml.followup_line_id IS NOT NULL
                   AND aml.parent_state = 'posted'
                   AND aml.reconciled IS NOT TRUE
                   AND aml.amount_residual > 0
                   AND aml.date_maturity IS NOT NULL
              GROUP BY aml.move_id
               ) due
         WHERE move.id = due.move_id
           AND move.last_auto_reminder IS NULL
        """
    )
    _logger.info("Set last_auto_reminder on %s invoices with a follow-up level", cr.rowcount)


def _activate_cron(env):
    # Settings turn it on when the switch is saved, and this script does not go through them.
    if not env["res.company"].search_count([("automatic_invoice_reminder", "=", True)], limit=1):
        return
    cron = env.ref("account_followup.ir_cron_follow_up", raise_if_not_found=False)
    if cron and not cron.active:
        cron.active = True
        _logger.info("Activated the follow-up cron")


def _emit(env, cr, levels, companies, branches):
    """The keys of the customer notes. All empty or zero on a database that did not use follow-up."""
    groups = {info["group"] for info in companies.values()}
    group = "automatic" if "automatic" in groups else "manual" if "manual" in groups else "unused"

    rows = []
    for company_id, info in companies.items():
        rows.append(_company_row(env, info, "", [level for level in levels if level["company_id"] == company_id]))
    for branch_id, source_id in branches.items():
        source = companies[source_id]
        branch = dict(source, name=env["res.company"].browse(branch_id).name)
        rows.append(
            _company_row(env, branch, source["name"], [level for level in levels if level["company_id"] == source_id])
        )

    used = group != "unused"
    manual_contacts = 0
    if used:
        cr.execute("SELECT count(*) FROM res_partner WHERE active AND followup_reminder_type = 'manual'")
        manual_contacts = cr.fetchone()[0]
    add_customer_note(
        cr,
        {
            "followup_companies": rows if group == "automatic" else [],
            "followup_to_activity_levels": (
                sum(
                    1
                    for level in levels
                    if companies[level["company_id"]]["group"] == "automatic" and _to_activity(level)
                )
                if group == "automatic"
                else 0
            ),
            "followup_manual_companies": (
                sorted(info["name"] for info in companies.values() if info["group"] == "manual")
                if group == "manual"
                else []
            ),
            "followup_branches": (
                [
                    {"name": env["res.company"].browse(branch_id).name, "parent": companies[source_id]["name"]}
                    for branch_id, source_id in branches.items()
                ]
                if used
                else []
            ),
            "followup_manual_contacts": manual_contacts,
            "followup_no_attach_levels": sum(1 for level in levels if not level["join_invoices"]) if used else 0,
            "followup_followers_levels": sum(1 for level in levels if level["followers"]) if used else 0,
        },
    )


def _company_row(env, info, branch_of, levels):
    return {
        "name": info["name"],
        "group": info["group"],
        "had_automatic": info["had_automatic"],
        "branch_of": branch_of,
        "levels": [
            {
                "days": level["delay"],
                "before": _before(env, level, info["lang"]),
                "after": _after(env, level, info["lang"]) if info["group"] == "automatic" else "Igual",
            }
            for level in levels
        ],
    }


def _template_name(env, model, template_id, lang):
    template = env[model].browse(template_id).exists() if template_id else None
    return template.with_context(lang=lang).name if template else None


def _media(env, level, lang):
    media = []
    if level["send_email"]:
        name = _template_name(env, "mail.template", level["mail_template_id"], lang)
        media.append("mail «%s»" % name if name else "mail")
    if level["send_sms"]:
        name = _template_name(env, "sms.template", level["sms_template_id"], lang)
        media.append("SMS «%s»" % name if name else "SMS")
    return media


def _before(env, level, lang):
    media = _media(env, level, lang) + (["actividad"] if level["create_activity"] else [])
    return "%s · %s" % ("Automático" if level["auto_execute"] else "Manual", ", ".join(media) or "sin medios")


def _after(env, level, lang):
    if not _to_activity(level):
        return "Igual"
    return "Actividad: mandar %s" % " y ".join(_media(env, level, lang))
