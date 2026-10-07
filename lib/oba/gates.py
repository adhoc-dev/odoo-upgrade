"""When a script that replaces an upgrade line runs, and the backup its pre_odoo half leaves.

    from oba import should_run

    def migrate(cr, version):
        if not should_run(cr, version, modules=["contacts"], position="last"):
            return

    from oba import create_backup, should_back_up

    def migrate(cr, version):
        if not should_back_up(cr, BACKUP_TABLE, modules=["account"]):
            return
        create_backup(cr, BACKUP_TABLE, "SELECT id, type FROM account_journal")

The conditions are the ones the provider checked before running the upgrade line: target
version, modules, position in the series, aim and a parameter of the ticket. Without a
request context (runbot, a local -u) the position and the aim do not filter, and a required
parameter is missing.

Public API: :func:`should_run`, :func:`should_back_up` and :func:`create_backup`.
"""

import logging
import re

from .request_context import request_context

_logger = logging.getLogger(__name__)

# Upgrades to 19 still run the upgrade lines: the scripts take over from 20.
FIRST_TARGET_VERSION = 20
POSITIONS = ("first", "last")


def should_run(
    cr,
    version,
    first_target=FIRST_TARGET_VERSION,
    last_target=None,
    modules=(),
    position=None,
    aim=None,
    parameter=None,
):
    """Whether a ``modules/base/0.0.0`` script runs on this ``-u``.

    :param version: what the script received; only a major jump runs
    :param first_target: lowest target version, the running Odoo
    :param last_target: highest target version, or ``None`` for no ceiling
    :param modules: all of them installed (``module_check_logic = all``)
    :param position: ``"first"`` or ``"last"`` request of the series, or ``None`` for any
    :param aim: ``"test"`` or ``"production"``, or ``None`` for both
    :param parameter: a ticket parameter that has to be set, or ``None``
    """
    _validate_position(position)
    # Here and not at the top: the pre_odoo scripts import oba with the Odoo of the source
    # version, and upgrade-util may not be there.
    from odoo import release
    from odoo.upgrade import util

    # A -u of base in the same version runs 0.0.0 too.
    if not _is_major_jump(version, release.version_info[0]):
        return False
    target = release.version_info[0]
    if not _in_target_range(target, first_target, last_target):
        return False
    for module in modules:
        if not util.module_installed(cr, module):
            _logger.info("%s is not installed: skipped", module)
            return False
    return _matches_request(request_context(cr), position, aim, parameter)


def should_back_up(cr, table, first_target=FIRST_TARGET_VERSION, last_target=None, modules=(), position=None):
    """Drop ``table`` and say whether a ``scripts/pre_odoo`` script backs up into it.

    The drop goes first: a table left by an earlier run must not reach a request that skips.
    Plain SQL, because it runs on the old database with the Odoo of the source version. The
    target comes from ``to_version``; outside a provider run there is none, and it backs up.

    :param table: the backup table, a constant of the script
    :param modules: all of them installed in the old database
    """
    _validate_position(position)
    cr.execute("DROP TABLE IF EXISTS %s" % table)

    context = request_context(cr)
    if context:
        # A provider that does not send to_version only upgrades to 19.
        target = re.search(r"\d+", context.get("to_version") or "")
        if not target:
            _logger.debug("No to_version in the request: %s not backed up", table)
            return False
        if not _in_target_range(int(target.group()), first_target, last_target):
            return False
    if modules:
        modules = tuple(modules)
        cr.execute(
            "SELECT count(*) FROM ir_module_module WHERE name IN %s AND state = 'installed'",
            (modules,),
        )
        if cr.fetchone()[0] != len(set(modules)):
            _logger.info("Not all of %s installed: %s not backed up", ", ".join(modules), table)
            return False
    return _matches_request(context, position, None, None)


def create_backup(cr, table, query, params=None, primary_key=("id",)):
    """Create ``table`` from ``query``, with its primary key.

    :param query: a ``SELECT``; its ``%s`` placeholders take ``params``. With ``params``, a
        literal ``%`` in the query goes as ``%%``
    :param primary_key: the columns of the key
    :returns: the number of rows backed up
    """
    cr.execute("CREATE TABLE %s AS %s" % (table, query), params)
    count = cr.rowcount
    # Without a PK, Odoo's test_ensure_has_pk flags it CRITICAL on every run.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (%s)" % (table, ", ".join(primary_key)))
    return count


def _is_major_jump(version, target):
    match = re.search(r"\d+", version or "")
    return bool(match) and int(match.group()) < target


def _in_target_range(target, first_target, last_target):
    # Debug: every 0.0.0 script asks on every jump, and most jumps are out of range.
    if target < first_target:
        _logger.debug("Not an upgrade to %s or later: the upgrade line handles it", first_target)
        return False
    if last_target is not None and target > last_target:
        _logger.debug("An upgrade to %s, after %s: not needed anymore", target, last_target)
        return False
    return True


def _validate_position(position):
    if position is not None and position not in POSITIONS:
        raise ValueError("position must be one of %s or None, got %r" % (POSITIONS, position))


def _matches_request(context, position, aim, parameter):
    _validate_position(position)
    if position and not context.get("is_%s_in_series" % position, True):
        _logger.info("Not the %s request of the series: skipped", position)
        return False
    if aim and context and context.get("aim") != aim:
        _logger.info("Not a %s request: skipped", aim)
        return False
    if parameter and not (context.get("parameters") or {}).get(parameter):
        _logger.info("Parameter %s not set: skipped", parameter)
        return False
    return True
