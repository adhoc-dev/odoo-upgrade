"""Origin and target of the major version jump in course.

    from oba import jump_versions

    def migrate(cr, version):
        from_version, to_version = jump_versions(version)  # ("18.0", "19.0")

Public API: :func:`jump_versions`.
"""

import os


def jump_versions(version):
    """``(from, to)`` versions of the jump in course, as ``("18.0", "19.0")``.

    The runner of the pass (``odoo_obaupgrade.py`` of ``saas_provider_upgrade``) declares them
    in the environment. Without them (a local run, runbot) the target is the Odoo running the
    ``-u`` and the origin, the installed ``base``.

    :param version: the ``version`` of ``migrate``, the installed ``base`` (``"18.0.1.3"``).
    """
    # Inside the function, so ``import oba`` does not need Odoo.
    from odoo.release import major_version

    from_version = os.environ.get("MYSCRIPT_FROM_VERSION") or "%s.0" % version.split(".")[0]
    to_version = os.environ.get("MYSCRIPT_TO_VERSION") or major_version
    return from_version, to_version
