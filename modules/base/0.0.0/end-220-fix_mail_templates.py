"""Bring back the mail templates the customer changed, and leave none that cannot be rendered.

Two steps, as the upgrade line 1211 did:

1. Restore. A template the customer changed (backed up by
   scripts/pre_odoo/always/220-backup_customer_mail_templates.py) that the upgrade put back to
   the standard gets its old ``body_html`` again, every language. Odoo's own render check
   decides if the old content still works; if it does not, the template keeps the standard
   and is reported as failed.
2. Render. Every other template the customer changed is rendered with the last records of
   its model, or compiled when there is none. One that fails with all of them is reset to the
   file of its module, or archived when it has none. One that fails only with some is left
   as it is: the error is in the data, not in the template.

The failed templates go to the customer note values as ``mail_templates_failed``: ``id`` in
this database, ``status`` and ``error``, the reason Odoo gave. ``R``: it has the standard of
this version; ``A``: archived; ``P``: fails only with some records, not touched. The Test &
C. Notes upgrade line of this version reads them, tells the Bugfix team in a subticket, and
applies the fixed code the team leaves in the ticket.

Only on the last request of a series. In ``modules/base/0.0.0`` so it runs on every jump,
after the modules are loaded, and after ``end-110``, which reloads the translations.
"""

import logging
from html import unescape

from lxml import html

from odoo.tools import SQL, mute_logger
from odoo.upgrade import util
from oba import add_customer_note, request_context, should_run

_logger = logging.getLogger(__name__)

# Created by scripts/pre_odoo/always/220-backup_customer_mail_templates.py, on the old database.
BACKUP_TABLE = "mail_template_customer_bu"
# Upgrades to 19 still run the upgrade line 1211.
FIRST_TARGET_VERSION = 20
# What the upgrade line rendered; without attachments and reports, so no report is rendered.
RENDER_FIELDS = [
    "subject", "body_html", "email_from", "email_to", "email_cc", "reply_to", "scheduled_date", "partner_to",
]
# Sent by Adhoc, not by the customer.
EXCLUDED_XMLIDS = ("base_install_request.mail_template_base_install_request",)
# Records to render each template with: one that fails only with some of them is not broken.
SAMPLE_SIZE = 3
RESET, ARCHIVED, PARTIAL = "R", "A", "P"
MUTED_LOGGERS = ("odoo.addons.mail.models.mail_render_mixin", "odoo.addons.mail.models.mail_template")


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["mail"], position="last"):
        return

    env = util.env(cr)
    ignored = _ignored_ids(env)
    langs = env["res.lang"].search([]).mapped("code")

    failed = {}
    samples = {}
    # A template that does not render is expected here and handled: Odoo would log each one as
    # an error with its traceback, and runbot fails a build on a traceback. The reason is
    # logged below, as info.
    with mute_logger(*MUTED_LOGGERS):
        restored = _restore(cr, env, ignored, langs, failed)
        _render(cr, env, ignored | set(failed), restored, langs, failed, samples)

    by_status = {
        status: sorted(tid for tid, (tid_status, _error) in failed.items() if tid_status == status)
        for status in (RESET, ARCHIVED, PARTIAL)
    }
    if any(by_status.values()):
        _logger.info(
            "Failed mail templates. With the standard: %s. Archived: %s. Only with some records: %s",
            by_status[RESET], by_status[ARCHIVED], by_status[PARTIAL],
        )

    # Always, also empty: the upgrade line tells "nothing failed" from "the script did not run".
    add_customer_note(
        cr,
        {
            "mail_templates_failed": [
                {"id": tid, "status": status, "error": error} for tid, (status, error) in sorted(failed.items())
            ]
        },
    )


def _restore(cr, env, ignored, langs, failed):
    """Put back the content of the customized templates the upgrade reset.

    :returns: the restored ids
    """
    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.info("No %s: no mail templates to restore", BACKUP_TABLE)
        return []

    # The upgrade wrote them: last change by OdooBot, and not the one in the old database.
    cr.execute(
        SQL(
            """
            SELECT t.id
              FROM mail_template t
              JOIN %s bu ON bu.id = t.id
             WHERE COALESCE(t.write_uid, 1) = 1
               AND t.write_date IS DISTINCT FROM bu.write_date
             ORDER BY t.id
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    template_ids = [row[0] for row in cr.fetchall() if row[0] not in ignored]
    # Without an active language, one check in the language of the environment.
    check_langs = langs or [None]
    templates = env["mail.template"].with_context(active_test=False)
    restored = []
    for template in templates.browse(template_ids):
        try:
            with cr.savepoint():
                # By SQL, to bring back every language as it was. Odoo's check runs below,
                # once per active language, as the write would have run it for one.
                cr.execute(
                    SQL(
                        """
                        UPDATE mail_template t
                           SET body_html = bu.body_html,
                               write_date = now() at time zone 'UTC'
                          FROM %s bu
                         WHERE bu.id = t.id
                           AND t.id = %s
                        """,
                        SQL.identifier(BACKUP_TABLE),
                        template.id,
                    )
                )
                template.invalidate_recordset(["body_html"])
                for lang in check_langs:
                    checked = template.with_context(lang=lang) if lang else template
                    checked._check_can_be_rendered(fnames={"body_html"})
        except Exception as e:
            error = _error_text(e)
            _logger.info("Mail template %s: the old content does not render here (%s)", template.id, error)
            template.invalidate_recordset(["body_html"])
            # Not archived: it keeps the standard of this version, which works.
            failed[template.id] = (RESET, error)
            continue
        restored.append(template.id)

    if restored:
        _logger.info("Mail templates restored with their content before the upgrade: %s", restored)
    if failed:
        _logger.info("Mail templates left with the standard, their old content does not render: %s", sorted(failed))
    return restored


def _render(cr, env, skipped, restored, langs, failed, samples):
    """Render the templates the customer changed; reset or archive the ones that fail."""
    # Active and changed by the customer: not last written by OdooBot. The restored ones are, now.
    cr.execute(
        """
        SELECT id
          FROM mail_template
         WHERE active
           AND (COALESCE(write_uid, 1) != 1 OR id = ANY(%s))
         ORDER BY id
        """,
        [restored],
    )
    template_ids = [row[0] for row in cr.fetchall() if row[0] not in skipped]
    if not template_ids:
        return

    render_context = _render_context(langs)
    for template in env["mail.template"].browse(template_ids):
        sample_ids = _sample_ids(cr, env, samples, template.model)
        # The restore check already rendered it with a record; without one it validated nothing.
        if template.id in restored and sample_ids:
            continue
        rendered = template.with_context(**render_context)
        error = _render_error(cr, env, rendered, sample_ids)
        if not error:
            continue
        # Fails with all of them? One by one, to tell a broken template from a broken record.
        errors = [error]
        if len(sample_ids) > 1:
            errors = [_render_error(cr, env, rendered, [record_id]) for record_id in sample_ids]
        if not any(errors):
            # Only the batch fails: no record is broken, and neither is the template.
            _logger.info("Mail template %s fails only rendered in batch, not touched (%s)", template.id, error)
            continue
        if not all(errors):
            failing = [record_id for record_id, record_error in zip(sample_ids, errors) if record_error]
            _logger.info(
                "Mail template %s fails only with some records of %s, not touched: %s (%s)",
                template.id, template.model, failing, error,
            )
            failed[template.id] = (PARTIAL, error)
            continue
        _logger.info("Mail template %s does not render (%s)", template.id, error)
        failed[template.id] = (_reset_or_archive(cr, template), error)


def _render_error(cr, env, template, record_ids):
    """Why ``template`` does not render with ``record_ids``, or None when it does."""
    try:
        with cr.savepoint():
            if record_ids:
                template._generate_template(record_ids, RENDER_FIELDS)
            elif template.body_html:
                # Without a record, parse the HTML and compile the QWeb, Odoo's first step
                # of a render. Not _has_unsafe_expression_template_qweb, the upgrade line's
                # check: it returns True on any expression of the template and raises nothing.
                env["ir.qweb"]._generate_code(html.fragment_fromstring(template.body_html, create_parent="div"))
    except Exception as e:
        return _error_text(e)
    return None


def _error_text(error):
    """What failed, for whoever fixes the template: the original error, ``SomeError: message``.

    Odoo wraps a render error, once or twice, in a long message that quotes the body of the
    template; the original one is at the end of the chain.
    """
    while error.__cause__ is not None or (error.__context__ is not None and not error.__suppress_context__):
        error = error.__cause__ or error.__context__
    lines = unescape(str(error)).strip().splitlines()
    return "%s: %s" % (type(error).__name__, (lines[0] if lines else "")[:300])


def _sample_ids(cr, env, samples, model):
    """The last records of ``model`` to render with, archived ones too as Odoo's own check.

    Searched once per model, and cached in ``samples``. A model the registry knows can still
    fail to search (a module half uninstalled): then there is no record, and the template is
    only compiled.
    """
    if not model or model not in env:
        return []
    if model not in samples:
        try:
            with cr.savepoint():
                ids = env[model].with_context(active_test=False).search([], limit=SAMPLE_SIZE, order="id desc").ids
        except Exception as e:
            _logger.info("Cannot search %s to render its mail templates (%s)", model, _error_text(e))
            ids = []
        samples[model] = ids
    return samples[model]


def _ignored_ids(env):
    """The template ids of the ticket parameter ``ignore_email_template``, and the excluded ones.

    The parameter is a list of ids, or a single one; an id written as text counts too.
    """
    value = (request_context(env.cr).get("parameters") or {}).get("ignore_email_template") or []
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    ignored = {int(item) for item in value if str(item).strip().isdigit()}
    for xmlid in EXCLUDED_XMLIDS:
        template = env.ref(xmlid, raise_if_not_found=False)
        if template:
            ignored.add(template.id)
    return ignored


def _render_context(langs):
    """The preview language, an active Spanish one; none forced when there is none.

    Odoo rejects a language that is not active. es_419 first, the standard we are taking every
    database to; then es_AR, for the ones that did not move yet.
    """
    for code in ("es_419", "es_AR"):
        if code in langs:
            return {"template_preview_lang": code}
    spanish = sorted(code for code in langs if code.startswith("es"))
    return {"template_preview_lang": spanish[0]} if spanish else {}


def _reset_or_archive(cr, template):
    """Reset a template that comes from a module file; archive it when it does not, or the reset fails."""
    # reset_template does nothing, silently, without template_fs.
    if template.template_fs:
        try:
            with cr.savepoint():
                # reset_template first writes the translations away, and that write renders the
                # broken content again and fails. Empty it first: the file brings it all back.
                columns = [
                    fname for fname in template._get_dynamic_field_names()
                    if fname in template._fields and template._fields[fname].store
                ]
                cr.execute(
                    SQL(
                        "UPDATE mail_template SET %s WHERE id = %s",
                        SQL(", ").join(SQL("%s = NULL", SQL.identifier(fname)) for fname in columns),
                        template.id,
                    )
                )
                template.invalidate_recordset(columns)
                template.reset_template()
                # Without its record in the file the reset does nothing, and the template stays empty.
                template.invalidate_recordset(columns)
                if not template.body_html:
                    raise ValueError("the file of its module does not have it")
            return RESET
        except Exception as e:
            template.invalidate_recordset()
            _logger.info("Mail template %s could not be reset (%s)", template.id, _error_text(e))
    # By SQL: the template does not render, and nothing has to validate it to archive it.
    cr.execute("UPDATE mail_template SET active = false WHERE id = %s", [template.id])
    template.invalidate_recordset(["active"])
    return ARCHIVED
