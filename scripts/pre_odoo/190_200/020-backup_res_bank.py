import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Odoo 20 removes res.bank from base: the upgrade drops the banks, their xmlids and the bank of
# each account and check. base_bank defines res.bank again in 20, so all of it is backed up here,
# whatever the localization, and restored on the other side of the upgrade by:
#   - modules/base_bank/20.0.1.0.0/post-migration.py: the banks with their ids and xmlids, and
#     the bank of each account;
#   - modules/l10n_latam_check_ux/20.0.1.0.0/post-migration.py: the bank of each check;
#   - modules/l10n_ar_bank/20.0.1.0.0/post-migration.py: the BCRA code.
BANK_TABLE = "res_bank_bu"
XMLID_TABLE = "res_bank_xmlid_bu"
BANK_NUMBER_TABLE = "res_bank_bank_number_bu"
ACCOUNT_TABLE = "res_partner_bank_bank_id_bu"
CHECK_TABLE = "l10n_latam_check_bank_id_bu"


def migrate(cr, version):
    """Back up the banks, their xmlids, and the bank of each bank account and check, before the pass.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if should_back_up(cr, BANK_TABLE, first_target=20, last_target=20):
        _logger.info("Backing up the banks into %s", BANK_TABLE)
        create_backup(
            cr,
            BANK_TABLE,
            """
            SELECT id, name, street, street2, zip, city, state, country, email, phone, active, bic,
                   create_uid, create_date, write_uid, write_date
              FROM res_bank
            """,
        )

    if should_back_up(cr, XMLID_TABLE, first_target=20, last_target=20):
        _logger.info("Backing up the xmlids of the banks into %s", XMLID_TABLE)
        create_backup(
            cr,
            XMLID_TABLE,
            "SELECT id, module, name, res_id, noupdate FROM ir_model_data WHERE model = 'res.bank'",
        )

    if should_back_up(cr, BANK_NUMBER_TABLE, first_target=20, last_target=20, modules=["l10n_ar_bank"]):
        _logger.info("Backing up the BCRA code of the banks into %s", BANK_NUMBER_TABLE)
        create_backup(
            cr,
            BANK_NUMBER_TABLE,
            "SELECT id, bank_number FROM res_bank WHERE bank_number IS NOT NULL",
        )

    if should_back_up(cr, ACCOUNT_TABLE, first_target=20, last_target=20):
        _logger.info("Backing up the bank of the bank accounts into %s", ACCOUNT_TABLE)
        create_backup(
            cr,
            ACCOUNT_TABLE,
            "SELECT id, bank_id FROM res_partner_bank WHERE bank_id IS NOT NULL",
        )

    if should_back_up(cr, CHECK_TABLE, first_target=20, last_target=20, modules=["l10n_latam_check"]):
        _logger.info("Backing up the bank of the checks into %s", CHECK_TABLE)
        create_backup(
            cr,
            CHECK_TABLE,
            "SELECT id, bank_id FROM l10n_latam_check WHERE bank_id IS NOT NULL",
        )
