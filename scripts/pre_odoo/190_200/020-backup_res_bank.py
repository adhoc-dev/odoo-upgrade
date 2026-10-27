import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Odoo 20 removes res.bank from base: the bank of an account becomes text, and the catalog,
# with the BCRA code that l10n_ar_bank adds, has nowhere to live. l10n_ar_bank 20 defines
# res.bank again, so the catalog and the links are backed up here and restored by
# modules/l10n_ar_bank/20.0.1.0.0/post-migration.py, on the other side of the upgrade.
BANK_TABLE = "res_bank_bu"
ACCOUNT_TABLE = "res_partner_bank_bank_id_bu"
# The bank of the checks is restored by the migration of l10n_latam_check_ux, not here.
CHECK_TABLE = "l10n_latam_check_bank_id_bu"


def migrate(cr, version):
    """Back up the banks, and the bank of each bank account and check, before the pass.

    Plain SQL on purpose: this runs on the old database, with the Odoo of the source version.
    """
    if should_back_up(cr, BANK_TABLE, first_target=20, last_target=20, modules=["l10n_ar_bank"]):
        _logger.info("Backing up the banks into %s", BANK_TABLE)
        create_backup(
            cr,
            BANK_TABLE,
            """
            SELECT b.id, b.name, b.street, b.street2, b.zip, b.city, b.state, b.country,
                   b.email, b.phone, b.active, b.bic, b.bank_number,
                   d.module AS xmlid_module, d.name AS xmlid_name
              FROM res_bank b
              LEFT JOIN ir_model_data d
                ON d.model = 'res.bank' AND d.res_id = b.id AND d.module = 'l10n_ar_bank'
            """,
        )

    if should_back_up(cr, ACCOUNT_TABLE, first_target=20, last_target=20, modules=["l10n_ar_bank"]):
        _logger.info("Backing up the bank of the bank accounts into %s", ACCOUNT_TABLE)
        create_backup(
            cr,
            ACCOUNT_TABLE,
            "SELECT id, bank_id FROM res_partner_bank WHERE bank_id IS NOT NULL",
        )

    if should_back_up(
        cr,
        CHECK_TABLE,
        first_target=20,
        last_target=20,
        modules=["l10n_ar_bank", "l10n_latam_check"],
    ):
        _logger.info("Backing up the bank of the checks into %s", CHECK_TABLE)
        create_backup(
            cr,
            CHECK_TABLE,
            "SELECT id, bank_id FROM l10n_latam_check WHERE bank_id IS NOT NULL",
        )
