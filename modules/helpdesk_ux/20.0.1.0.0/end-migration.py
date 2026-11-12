import logging

from odoo.tools import SQL
from odoo.upgrade import util
from oba import add_customer_note

_logger = logging.getLogger(__name__)

# What a rating request looks like inside a mail template body: the token and the /rate/ link.
RATING_MARKERS = ["%_rating_get_access_token%", "%/rate/%"]


def migrate(cr, version):
    # In 20 a stage sends its own rating request ("Ask for Ratings"). Up to 19 it travelled inside
    # the stage email template. If the jump leaves both on, the customer gets two surveys: list
    # those stages for the customer note. Runs in end- so Odoo's own helpdesk scripts are done.
    if not util.column_exists(cr, "helpdesk_stage", "rating_active"):
        _logger.warning(
            "helpdesk_stage.rating_active not found: duplicated rating survey not checked"
        )
        return

    admin_id = util.ref(cr, "base.user_admin")
    lang = "en_US"
    if admin_id:
        cr.execute(
            """
            SELECT p.lang
              FROM res_users u
              JOIN res_partner p ON p.id = u.partner_id
             WHERE u.id = %s
            """,
            [admin_id],
        )
        row = cr.fetchone()
        lang = (row and row[0]) or lang

    cr.execute(
        SQL(
            """
            SELECT COALESCE(s.name ->> %(lang)s, s.name ->> 'en_US'),
                   COALESCE(t.name ->> %(lang)s, t.name ->> 'en_US')
              FROM helpdesk_stage s
              JOIN mail_template t ON t.id = s.template_id
             WHERE s.active
               AND s.rating_active
               AND t.body_html::text ILIKE ANY(%(markers)s)
             ORDER BY s.sequence, s.id
            """,
            lang=lang,
            markers=RATING_MARKERS,
        )
    )
    stages = [{"name": name, "template": template} for name, template in cr.fetchall()]
    _logger.info(
        "%s helpdesk stages ask for ratings and also carry the survey in their template",
        len(stages),
    )
    # Also with none: it overwrites what an earlier jump left, and the note is not created.
    add_customer_note(cr, {"helpdesk_rating_duplicated_stages": stages})
