import logging

_logger = logging.getLogger(__name__)

# Invoice lines with the discounts of sale_three_discounts (18). The install of
# account_invoice_triple_discount in 19 rewrites them in its post_init_hook, and
# scripts/pre_upgrade/180_190/account_invoice_triple_discount_keep_discounts.py keeps them.
# Checked by modules/sale_triple_discount/tests/expected_190.py.
MODULE = "upgrade_prepare_demo"
# A discount over 100 that the sale_three_discounts constraint never saw: it was stored in
# discount alone, as in the old invoices of real databases.
DISCOUNT_OVER_100 = 676.28


def migrate(env):
    if "discount1" not in env["account.move.line"]._fields:
        _logger.info("No sale_three_discounts in this database: nothing seeded")
        return

    env["account.move"]._load_records(
        [
            {
                "xml_id": "%s.move_triple_discounts" % MODULE,
                "values": {
                    "move_type": "out_invoice",
                    "partner_id": env.company.partner_id.id,
                },
                "noupdate": True,
            }
        ]
    )
    move = env.ref("%s.move_triple_discounts" % MODULE)
    lines = env["account.move.line"]._load_records(
        [
            {
                "xml_id": "%s.aml_two_discounts" % MODULE,
                "values": {
                    "move_id": move.id,
                    "name": "Two discounts (upgrade test)",
                    "quantity": 1.0,
                    "price_unit": 100.0,
                    "discount1": 10.0,
                    "discount2": 20.0,
                },
                "noupdate": True,
            },
            {
                "xml_id": "%s.aml_discount_over_100" % MODULE,
                "values": {
                    "move_id": move.id,
                    "name": "Discount over 100 (upgrade test)",
                    "quantity": 1.0,
                    "price_unit": 1.0,
                },
                "noupdate": True,
            },
        ]
    )
    env.flush_all()
    env.cr.execute(
        "UPDATE account_move_line SET discount = %s, discount1 = 0, discount2 = 0, discount3 = 0 WHERE id = %s",
        (DISCOUNT_OVER_100, lines[1].id),
    )
    env.invalidate_all()
    _logger.info("Seeded 2 invoice lines for the triple discount checks")
