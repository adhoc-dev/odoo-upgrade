"""Unlink from each mail template the reports of another model.

Some upgraded databases have standard templates whose ``report_template_ids`` point to a
report of another model: the user invitation with the payment receipt, for example. Sending
the template renders the report name on a record of the template model, and the mail fails.
The form hides the field when no report of the template model exists, so the customer
cannot remove it.

Only the link goes away; the template content is not touched. The form offers the same
pairs: a report of the template model. A template without a model keeps its reports.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from oba import should_run, timed

_logger = logging.getLogger(__name__)

# report_template_ids exists since 17.
FIRST_TARGET_VERSION = 17


@timed
def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["mail"]):
        return

    cr.execute(
        """
        DELETE FROM mail_template_ir_actions_report_rel rel
         USING mail_template t, ir_act_report_xml r
         WHERE t.id = rel.mail_template_id
           AND r.id = rel.ir_actions_report_id
           AND r.model <> t.model
     RETURNING rel.mail_template_id, rel.ir_actions_report_id
        """
    )
    pairs = sorted(cr.fetchall())
    if pairs:
        _logger.info("Reports of another model unlinked from mail templates (template, report): %s", pairs)
