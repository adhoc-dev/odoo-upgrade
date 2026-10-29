# Test declarativo de los bancos en el salto a 20, que saca res.bank de base.
#
# scripts/pre_odoo/190_200/020-backup_res_bank.py respalda en la base 19 los bancos, sus
# xmlids, el codigo BCRA y el banco de cada cuenta y de cada cheque. Lo restauran:
#   base_bank/20.0.1.0.0/post-migration.py           bancos con su id y su xmlid, banco de la cuenta
#   l10n_latam_check_ux/20.0.1.0.0/post-migration.py banco del cheque
#   l10n_ar_bank/20.0.1.0.0/post-migration.py        codigo BCRA, y fusion con los bancos nuevos
#                                                    del catalogo
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007). La base llega preparada por
# tests/pre_odu/l10n_ar_bank/190_200/010-banks.py. Que los xmlids upgrade_prepare_demo.* de
# los bancos resuelvan ya prueba que se restauraron: el pase de Odoo los borra con el modelo.

EXPECTED = {
    "res.bank": {
        # Banco del catalogo: vuelve por su xmlid de l10n_ar_bank y toma el codigo de la data.
        # Si falta, el catalogo se creo de nuevo en vez de actualizar el banco de 19.
        ref("l10n_ar_bank.00007"): {
            "bank_number": "007",
        },
        # Banco a mano: vuelve con sus datos y su codigo BCRA de 19. Si el codigo viene vacio,
        # no se restauro desde res_bank_bank_number_bu.
        ref("upgrade_prepare_demo.bank_by_hand"): {
            "name": "Banco cargado a mano",
            "bic": "MANUAL01",
            "bank_number": "990",
            "active": True,
        },
        # Preservacion: un banco archivado en 19 sigue archivado.
        ref("upgrade_prepare_demo.bank_archived"): {
            "bank_number": "991",
            "active": False,
        },
        # Banco a mano con el codigo de un banco nuevo del catalogo de 20: se fusiona y su xmlid
        # pasa al banco del catalogo. Si conserva su nombre, quedaron dos bancos con el codigo 384.
        ref("upgrade_prepare_demo.bank_uala_by_hand"): {
            "name": "UALA BANK S.A.U.",
            "bank_number": "384",
        },
    },
    "res.partner.bank": {
        # Cada cuenta vuelve a su banco, con el codigo BCRA como numero de compensacion. Si el
        # banco viene vacio, se perdio el vinculo del pase.
        ref("upgrade_prepare_demo.account_catalog_bank"): {
            "bank_id": ref("l10n_ar_bank.00007"),
            "clearing_number": "007",
            "clearing_label_id": ref("l10n_ar_bank.clearing_label_ar"),
        },
        ref("upgrade_prepare_demo.account_bank_by_hand"): {
            "bank_id": ref("upgrade_prepare_demo.bank_by_hand"),
            "bank_name": "Banco cargado a mano",
            "clearing_number": "990",
        },
        ref("upgrade_prepare_demo.account_bank_archived"): {
            "bank_id": ref("upgrade_prepare_demo.bank_archived"),
        },
        # La cuenta del banco fusionado pasa al banco del catalogo.
        ref("upgrade_prepare_demo.account_bank_uala_by_hand"): {
            "bank_id": ref("l10n_ar_bank.00384"),
            "clearing_number": "384",
        },
    },
    "l10n_latam.check": {
        # Cheque de terceros con banco y sin cuenta: vuelve al banco de 19. Si viene vacio, el
        # banco del cheque se perdio con res.bank.
        ref("upgrade_prepare_demo.check_bank_without_account"): {
            "bank_id": ref("upgrade_prepare_demo.bank_by_hand"),
        },
    },
}
