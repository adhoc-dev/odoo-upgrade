"""Replace the release note Odoo posts on each jump with our success message.

The Odoo upgrade posts its release note in the general channel once per jump
(``util.announce_release_note``). The newest one takes our message, from
``success_upgrade_message.html`` with ``{version}`` replaced by the target version, and the
ones of the other jumps of this request are deleted, as many as the request jumps. Release
notes of earlier upgrades stay. Without a request context, only the newest is replaced.

``{image}`` takes the image of the target version, ``success_upgrade_images/<major>.png``,
attached to the general channel. Without that file the message goes without image.

The release notes are found by the text of their template, not by date: other messages of
the channel are not touched.

Only on the last jump of the request.

In ``modules/base/0.0.0`` so it runs on every jump, after the modules are loaded.
"""

import logging
import os
import re

from markupsafe import Markup

from odoo import release
from odoo.upgrade import util
from oba import log_message, request_context, should_run

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade line 1491.
FIRST_TARGET_VERSION = 20
MESSAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "success_upgrade_message.html")
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "success_upgrade_images")
# From release-note.xml of upgrade-util, the same since the template exists.
RELEASE_NOTE_TEXT = "Your database has successfully been upgraded to the latest version"


def migrate(cr, version):
    # Only on a major upgrade.
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["mail"], position="last"):
        return

    with open(MESSAGE_PATH, encoding="utf-8") as f:
        # replace, not format: the HTML may carry other braces.
        template = f.read().replace("{version}", release.major_version)

    env = util.env(cr)
    channel = env.ref("mail.channel_all_employees", raise_if_not_found=False)
    if not channel:
        _logger.info("No general channel: no release note to replace")
        return

    messages = env["mail.message"].search(
        [
            ("model", "=", channel._name),
            ("res_id", "=", channel.id),
            ("body", "ilike", RELEASE_NOTE_TEXT),
        ],
        order="id desc",
    )
    if not messages:
        _logger.info("No release note of Odoo in the general channel")
        return

    # Odoo posts one per jump: this request's are the newest, as many as it jumps.
    jumps = _jumps(request_context(cr))
    to_drop = messages[1:jumps]
    try:
        with cr.savepoint():
            body = Markup(template.replace("{image}", _image_tag(env, channel)))
            messages[0].write({"body": body})
            to_drop.unlink()
    except Exception as e:
        log_message(cr, "Could not replace the release notes %s: %s" % (messages[:jumps].ids, e), "warning")
        return
    _logger.info("Release note %s replaced, %s dropped", messages[0].id, to_drop.ids)


def _image_tag(env, channel):
    """The image of the target version as an HTML paragraph, empty when there is none."""
    path = os.path.join(IMAGES_DIR, "%s.png" % release.version_info[0])
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        raw = f.read()
    attachment = env["ir.attachment"].create(
        {
            "name": os.path.basename(path),
            "raw": raw,
            "mimetype": "image/png",
            "res_model": channel._name,
            "res_id": channel.id,
        }
    )
    token = attachment.generate_access_token()[0]
    return '<p><img src="/web/image/%s?access_token=%s" alt="Odoo By Adhoc %s"/></p>' % (
        attachment.id,
        token,
        release.major_version,
    )


def _jumps(context):
    """How many major versions this request jumps, 1 when the context does not say."""
    origin = re.search(r"\d+", context.get("from_version") or "")
    if not origin:
        return 1
    return max(release.version_info[0] - int(origin.group()), 1)
