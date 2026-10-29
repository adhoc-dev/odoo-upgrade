import logging

_logger = logging.getLogger(__name__)

# Casos de los bancos en el salto a 20, que saca res.bank de base. Los respalda
# scripts/pre_odoo/190_200/020-backup_res_bank.py y los restauran los post-migration de
# base_bank, l10n_latam_check_ux y l10n_ar_bank. Los verifica
# modules/l10n_ar_bank/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: el catalogo de l10n_ar_bank ya esta en la base canonica, pero no
# un banco cargado a mano, uno archivado ni uno a mano que el catalogo de 20 trae como banco
# nuevo. Tampoco cuentas con banco ni un cheque con banco y sin cuenta.
#
#   banco del catalogo (Galicia, 007)  -> vuelve por su xmlid, actualizado desde el catalogo
#   banco a mano (990)                 -> vuelve con su id, su xmlid y su codigo BCRA
#   banco archivado a mano (991)       -> vuelve archivado
#   banco a mano con el codigo 384     -> se fusiona con el banco nuevo del catalogo (Uala)
BANKS = [
    ("bank_by_hand", {"name": "Banco cargado a mano", "bic": "MANUAL01", "bank_number": "990"}),
    ("bank_archived", {"name": "Banco archivado a mano", "bank_number": "991", "active": False}),
    ("bank_uala_by_hand", {"name": "Uala cargado a mano", "bank_number": "384"}),
]
ACCOUNTS = [
    # (xmlid, numero de cuenta, xmlid del banco)
    ("account_catalog_bank", "0070001000000000000001", "l10n_ar_bank.00007"),
    ("account_bank_by_hand", "9900001000000000000001", "upgrade_prepare_demo.bank_by_hand"),
    ("account_bank_archived", "9910001000000000000001", "upgrade_prepare_demo.bank_archived"),
    ("account_bank_uala_by_hand", "3840001000000000000001", "upgrade_prepare_demo.bank_uala_by_hand"),
]
CHECK_XMLID = "check_bank_without_account"


def _seed_check(env):
    # Un cheque de terceros endosado suele no tener cuenta del emisor: el banco es lo unico que
    # queda. No se crea un pago: se toma un cheque de terceros de la base canonica.
    if env["ir.model.data"].search_count([("module", "=", "upgrade_prepare_demo"), ("name", "=", CHECK_XMLID)]):
        return
    check = env["l10n_latam.check"].search(
        [("payment_method_line_id.code", "=", "new_third_party_checks")], order="id", limit=1
    )
    if not check:
        # Sin cheque no hay caso: lo dice el check como ref ausente
        _logger.info("No third party check in this database - not seeding the bank of a check")
        return
    check.write({"bank_id": env.ref("upgrade_prepare_demo.bank_by_hand").id})
    env["ir.model.data"].create(
        {
            "module": "upgrade_prepare_demo",
            "name": CHECK_XMLID,
            "model": "l10n_latam.check",
            "res_id": check.id,
            "noupdate": True,
        }
    )


def migrate(env):
    if not env.ref("l10n_ar_bank.00007", raise_if_not_found=False):
        _logger.info("l10n_ar_bank no esta en esta base - no se siembra nada")
        return
    env["res.bank"]._load_records(
        [{"xml_id": "upgrade_prepare_demo.%s" % name, "values": values, "noupdate": True} for name, values in BANKS]
    )
    partner = env["res.partner"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.partner_with_bank_accounts",
                "values": {"name": "Contacto con cuentas bancarias", "country_id": env.ref("base.ar").id},
                "noupdate": True,
            }
        ]
    )
    env["res.partner.bank"]._load_records(
        [
            {
                "xml_id": "upgrade_prepare_demo.%s" % name,
                "values": {"partner_id": partner.id, "acc_number": number, "bank_id": env.ref(bank).id},
                "noupdate": True,
            }
            for name, number, bank in ACCOUNTS
        ]
    )
    if "l10n_latam.check" in env:
        _seed_check(env)
    _logger.info("Seeded %s banks and %s bank accounts for the res.bank backup", len(BANKS), len(ACCOUNTS))
