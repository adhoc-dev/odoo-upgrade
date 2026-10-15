"""Turn the account groups into archived parent accounts, as the charts of 20 do.

Reads what scripts/pre_odoo/always/220-backup_account_groups.py backed up on the old
database. 20 drops ``account.group``, and its charts ship each group as an archived account
that only groups other accounts, with the xmlid the group had. This builds the same thing
for the groups of the database: the ones of a chart keep their xmlid, so a later update of
the chart finds them instead of creating them again.

A root company where some account already has a parent is left as it is: the upgrade, or an
earlier run of this script, already built the hierarchy.

In ``modules/base/0.0.0`` so it runs after the modules are loaded.
"""

import logging
from collections import defaultdict

from odoo.tools import SQL
from odoo.upgrade import util
from oba import log_message, should_run

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "account_group_bu"
# Same range as the pre_odoo script: 20 is the version that drops account.group.
FIRST_TARGET_VERSION = 20
LAST_TARGET_VERSION = 20
# A parent account takes the type of its first account, except the types that carry a rule:
# a cash or credit card account gets a journal on create, a receivable or payable one is
# reconcilable, and there is only one current year earnings account per company.
PARENT_TYPES = {
    "asset_cash": "asset_current",
    "asset_receivable": "asset_current",
    "liability_credit_card": "liability_current",
    "liability_payable": "liability_current",
    "equity_unaffected": "equity",
}


def migrate(cr, version):
    # Only on a major upgrade. The table stays until the next pre_odoo run: a repeated -u
    # finds the hierarchy already built and skips.
    if not should_run(cr, version, FIRST_TARGET_VERSION, LAST_TARGET_VERSION, modules=["account"]):
        return

    if not util.table_exists(cr, BACKUP_TABLE):
        _logger.warning("No %s: the account groups were not turned into parent accounts", BACKUP_TABLE)
        return

    cr.execute(
        SQL(
            """
            SELECT id, company_id, parent_id, code_prefix_start, code_prefix_end, xmlid_module, xmlid_name
              FROM %s
            """,
            SQL.identifier(BACKUP_TABLE),
        )
    )
    groups_by_company = defaultdict(list)
    for group in cr.dictfetchall():
        group["code_prefix_end"] = group["code_prefix_end"] or group["code_prefix_start"]
        groups_by_company[group["company_id"]].append(group)

    env = util.env(cr)
    for company in env["res.company"].browse(sorted(groups_by_company)).exists():
        try:
            with cr.savepoint():
                _convert_groups(env, company, groups_by_company[company.id])
        except Exception as e:
            _logger.exception("The account groups of %s were not converted", company.name)
            log_message(
                cr,
                "The account groups of %s were not turned into parent accounts: %s" % (company.name, e),
                "error",
            )


def _convert_groups(env, company, groups):
    """Create an archived parent account per group of ``company``, and hang the accounts from them."""
    Account = env["account.account"].with_company(company).with_context(active_test=False, tracking_disable=True)
    accounts = Account.search([("company_ids", "child_of", company.id)])
    if any(accounts.mapped("parent_id")):
        _logger.info("%s already has parent accounts: its groups are not converted", company.name)
        return

    codes = set(accounts.filtered("code").mapped("code"))
    groups_by_id = {group["id"]: group for group in groups}
    parent_by_group = {}
    # A parent group always has a shorter prefix than its children, so it is created first.
    for group in sorted(groups, key=lambda g: (len(g["code_prefix_start"]), g["code_prefix_start"])):
        members = accounts.filtered(lambda a, g=group: _in_group(a.code, g)).sorted("code")
        if not members:
            # As the charts of 20: a group without accounts has no type to take.
            _logger.info("Account group %s of %s has no accounts: skipped", group["id"], company.name)
            continue
        parent_by_group[group["id"]] = _create_parent_account(
            Account, company, group, members[0], codes, _created_ancestor(group, groups_by_id, parent_by_group)
        )

    accounts_by_parent = defaultdict(list)
    deepest_first = sorted(
        (groups_by_id[group_id] for group_id in parent_by_group),
        key=lambda g: len(g["code_prefix_start"]),
        reverse=True,
    )
    for account in accounts:
        group = next((g for g in deepest_first if _in_group(account.code, g)), None)
        if group:
            accounts_by_parent[parent_by_group[group["id"]]].append(account.id)
    for parent, account_ids in accounts_by_parent.items():
        Account.browse(account_ids).write({"parent_id": parent.id})

    _logger.info(
        "%s: %s account groups turned into parent accounts, %s accounts hung from them",
        company.name,
        len(parent_by_group),
        sum(len(ids) for ids in accounts_by_parent.values()),
    )


def _create_parent_account(Account, company, group, first_member, codes, parent):
    start, end = group["code_prefix_start"], group["code_prefix_end"]
    code = start if start == end else "%s-%s" % (start, end)
    # Same as the charts of 20: the group takes no code when an account already has it.
    if start == end and start in codes:
        code = False
    account = Account.create(
        {
            "name": start,
            "code": code,
            "account_type": PARENT_TYPES.get(first_member.account_type, first_member.account_type),
            "active": False,
            "company_ids": [company.id],
            "parent_id": parent.id if parent else False,
        }
    )
    # The name with all its translations, as the group had it.
    Account.env.cr.execute(
        SQL(
            "UPDATE account_account SET name = bu.name FROM %s bu WHERE account_account.id = %s AND bu.id = %s",
            SQL.identifier(BACKUP_TABLE),
            account.id,
            group["id"],
        )
    )
    account.invalidate_recordset(["name"])
    if group["xmlid_module"]:
        _move_xmlid(Account.env, group, account)
    return account


def _move_xmlid(env, group, account):
    """Give ``account`` the xmlid of its group, the one the chart of 20 uses for it."""
    data = (
        env["ir.model.data"]
        .sudo()
        .search([("module", "=", group["xmlid_module"]), ("name", "=", group["xmlid_name"])], limit=1)
    )
    values = {"model": "account.account", "res_id": account.id, "noupdate": True}
    if data:
        data.write(values)
    else:
        env["ir.model.data"].sudo().create(
            dict(values, module=group["xmlid_module"], name=group["xmlid_name"])
        )


def _created_ancestor(group, groups_by_id, parent_by_group):
    """The parent account of the closest ancestor group that got one."""
    parent_id = group["parent_id"]
    while parent_id:
        if parent_id in parent_by_group:
            return parent_by_group[parent_id]
        parent_id = groups_by_id.get(parent_id, {}).get("parent_id")
    return None


def _in_group(code, group):
    """Same match as the account groups of 19: the prefix of the code falls in the range."""
    if not code:
        return False
    start = group["code_prefix_start"]
    return start <= code[: len(start)] <= group["code_prefix_end"]
