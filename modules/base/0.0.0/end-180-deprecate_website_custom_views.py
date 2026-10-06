"""Deprecate the website views customized by the customer, so the website takes the standard ones.

Almost every customer has these views modified, and the old copy breaks the website on the new
version. A view is taken when it is qweb, has a key and a website, is not a page and is not in
``IGNORE_KEYS``; its inherited views go with it. Each one is deactivated and its key gets
``_depreciada``, so the customer note can show the diff against the standard view. Then the
views of ``UNDEPRECATE_KEYS`` are recovered on ``website.layout``.

Writes by SQL: a write on ``ir.ui.view`` validates the combined arch, and an orphan view with
an xpath that no longer exists aborts the whole script. The searches go by ORM, reading does not
validate. Idempotent: a deprecated key is not deprecated again.

The customer note with the diff of each view is not here: it is the test upgrade line, which
finds the views by the ``_depreciada`` key.

Only on the last jump of the request, with ``website`` installed.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging

from odoo.upgrade import util
from oba import should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 664.
FIRST_TARGET_VERSION = 20
SUFFIX = "_depreciada"
IGNORE_KEYS = [
    "saas_provider_adhoc.support_chat",
    "website.footer_custom",
    "website_sale.products_categories",
    "website.header_search_box",
    "website.header_text_element",
    "mass_mailing.s_mail_block_header_social",
    "mass_mailing.s_mail_block_header_text_social",
    "mass_mailing.s_mail_block_header_logo",
    "mass_mailing.s_mail_block_header_view",
    "website.template_header_mobile",
    "website.template_header_default",
    "website.placeholder_header_brand",
    "website.option_header_brand_logo",
    "website.header_visibility_standard",
    "website.placeholder_header_language_selector",
    "website.header_language_selector",
    "website.placeholder_header_call_to_action",
    "website.header_call_to_action",
    "website.header_call_to_action_large",
    "website.header_call_to_action_sidebar",
    "website.header_call_to_action_stretched",
    "website.placeholder_header_social_links",
    "website.header_search_box_input",
    "website.placeholder_header_search_box",
    "website.placeholder_header_text_element",
    "website.snippet_options_header_box",
    "website_sale.header_cart_link",
    "website_sale.template_header_mobile",
    "website_sale.template_header_default",
    "website_sale.template_header_hamburger",
    "website_sale.template_header_stretch",
    "website_sale.template_header_vertical",
    "website_sale.template_header_search",
    "portal.portal_my_home",
    "account.account_terms_conditions_page",
    "website.cookie_policy",
    "website.aboutus",
    "website.privacy_policy",
    "website_hr_recruitment.index",
    "website_hr_recruitment.detail",
    "website_hr_recruitment.thankyou",
    "appointment.portal_my_home_appointment",
    "account_payment.portal_my_home_account_payment",
    "sale.portal_my_home_sale",
    "purchase.portal_my_home_purchase",
    "account.portal_my_home_invoice",
    "project.portal_my_home",
    "hr_timesheet.portal_my_home_timesheet",
    "helpdesk.portal_my_home_helpdesk_ticket",
    "payment.portal_my_home_payment",
    "sale_subscription.portal_my_home_subscription",
    "documents.portal_my_home_documents",
    "website_sale.products_oe_structure_website_sale_products_1",
    "website_sale.products_oe_structure_website_sale_products_2",
    "website_sale.product_oe_structure_website_sale_product_1",
    "website_sale.product_oe_structure_website_sale_product_2",
    "website_hr_recruitment.apply",
    "website_sale.product_custom_text",
    "website.template_footer_minimalist",
    "website.template_footer_contact",
    "website.footer_copyright_company_name",
    "website_sale.header_hide_empty_cart_link",
    "website_sale_wishlist.header_hide_empty_wishlist_link",
    "website_sale.products_categories_top",
]
# Deprecated only because they inherit from a deprecated view, and wanted back.
UNDEPRECATE_KEYS = ["website.footer_custom" + SUFFIX]


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["website"], position="last"):
        return

    View = util.env(cr)["ir.ui.view"].with_context(active_test=False)
    views = View.search(
        [
            ("type", "=", "qweb"),
            ("key", "not in", IGNORE_KEYS),
            ("key", "not like", "%" + SUFFIX),
            ("key", "!=", False),
            ("page_ids", "=", False),
            ("website_id", "!=", False),
        ]
    )
    view_ids = views.ids
    children = views
    while children:
        children = View.search([("inherit_id", "in", children.ids), ("id", "not in", view_ids)])
        view_ids.extend(children.ids)

    if view_ids:
        cr.execute(
            """
            UPDATE ir_ui_view
               SET key = CASE WHEN right(key, %s) = %s THEN key ELSE key || %s END,
                   active = false
             WHERE id = ANY(%s)
            """,
            (len(SUFFIX), SUFFIX, SUFFIX, view_ids),
        )
        _logger.info("Deprecated %s customized website views: %s", len(view_ids), sorted(view_ids))

    cr.execute("SELECT id FROM ir_ui_view WHERE key = 'website.layout' AND website_id IS NULL LIMIT 1")
    layout = cr.fetchone()
    if layout:
        cr.execute(
            """
            UPDATE ir_ui_view
               SET key = replace(key, %s, ''), active = true, mode = 'extension', inherit_id = %s
             WHERE NOT active
               AND key = ANY(%s)
               AND type = 'qweb'
               AND website_id IS NOT NULL
            """,
            (SUFFIX, layout[0], UNDEPRECATE_KEYS),
        )
