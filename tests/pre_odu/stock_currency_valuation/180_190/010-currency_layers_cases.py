import logging

from odoo import fields

_logger = logging.getLogger(__name__)

# Valuation layers of stock_currency_valuation (18 -> 19). In 18 the value in the
# valuation currency lives in stock.valuation.layer, which 19 drops. Each case runs the
# real 18 flow on its own product (default_code SCV-Cnn), so every layer of a product
# belongs to one case. The cases mirror the layer types of a real customer base.
#
# BACKUP_TABLE keeps a copy of those layers so they can be compared with what the
# upgrade leaves in stock.move and product.value.

PREFIX = "upgrade_prepare_demo.scv_"
BACKUP_TABLE = "upgrade_test_scv_layers"
# ARS per USD, apart from the system rate so a manual rate is easy to spot.
PICKING_RATE = 1450.0
LANDED_COST_RATE = 1480.0
FALLBACK_USD_RATE = 1400.0


def migrate(env):
    if "value_in_currency" not in env["stock.valuation.layer"]._fields:
        _logger.info("stock_currency_valuation no esta en esta base — no se siembra nada")
        return
    company = _company(env, env.ref("base.USD"))
    if not company:
        _logger.info("No hay una compania en otra moneda que USD — no se siembra nada")
        return
    _logger.info("Se siembra en la compania %s (%s)", company.name, company.currency_id.name)
    # Every record created below defaults to the seeded company.
    env = env(context=dict(env.context, allowed_company_ids=company.ids))
    ctx = _setup(env)
    env.cr.commit()
    for key, label, needs_sale, case in CASES:
        if env.ref(PREFIX + key, raise_if_not_found=False):
            continue
        if needs_sale and "sale.order" not in env:
            _logger.info("Caso %s: sin ventas en esta base, se saltea", key)
            continue
        # Commit per case instead of a savepoint: some flows of the seed base commit on
        # their own, which drops any savepoint and would abort the other seeds too.
        try:
            case(env, ctx, key, label)
            env.cr.commit()
        except Exception:
            env.cr.rollback()
            env.invalidate_all()
            _logger.exception("Caso %s (%s): fallo la siembra", key, label)
    _backup_layers(env)


# --------------------------------------------------------------------- setup


def _company(env, usd):
    """A main company with a warehouse and not in USD; an Argentine RI one first,
    as the customers of the module."""
    candidates = env["stock.warehouse"].search([]).company_id.filtered(
        lambda c: c.currency_id != usd and not c.parent_id
    )
    return candidates.sorted(
        lambda c: (c.chart_template != "ar_ri", c.currency_id.name != "ARS", c.id)
    )[:1]


def _setup(env):
    usd = env.ref("base.USD").with_context(active_test=False)
    company = env.company
    usd.active = True
    if not env["res.currency.rate"].search_count([("currency_id", "=", usd.id), ("company_id", "in", [company.id, False])]):
        env["res.currency.rate"].create({"currency_id": usd.id, "rate": 1 / FALLBACK_USD_RATE, "company_id": company.id})

    # Real-time valuation, as the customers that use the module: the journal entries
    # also carry the amount in currency. Some charts (l10n_ar) bring no stock accounts.
    all_categ = env.ref("product.product_category_all").with_company(company)
    accounts = {
        "property_stock_valuation_account_id": all_categ.property_stock_valuation_account_id
        or _account(env, company, "account_valuation", "SCV01", "Stock valuado SCV (upgrade test)", False),
        "property_stock_account_input_categ_id": all_categ.property_stock_account_input_categ_id
        or _account(env, company, "account_input", "SCV02", "Stock recibido sin facturar SCV (upgrade test)", True),
        "property_stock_account_output_categ_id": all_categ.property_stock_account_output_categ_id
        or _account(env, company, "account_output", "SCV03", "Stock entregado sin facturar SCV (upgrade test)", True),
        "property_stock_journal": all_categ.property_stock_journal
        or env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1),
    }
    accounts = {field: record.id for field, record in accounts.items()}

    categ_usd = _load(env, "product.category", "categ_usd", dict(
        accounts, name="Valuacion en USD (upgrade test)", property_cost_method="average",
        property_valuation="real_time", valuation_currency_id=usd.id,
    ))
    categ_none = _load(env, "product.category", "categ_none", dict(
        accounts, name="Sin moneda de valuacion (upgrade test)", property_cost_method="average",
        property_valuation="real_time",
    ))
    expense = env["account.account"].search(
        [("account_type", "=", "expense"), ("company_ids", "in", company.id)], limit=1
    )
    landed_product = _load(env, "product.product", "landed_cost_product", {
        "name": "Flete de importacion (upgrade test)", "type": "service", "landed_cost_ok": True,
        "split_method_landed_cost": "by_quantity", "property_account_expense_id": expense.id,
    })
    vendor = _load(env, "res.partner", "vendor", {"name": "Proveedor SCV (upgrade test)"})
    customer = _load(env, "res.partner", "customer", {"name": "Cliente SCV (upgrade test)"})
    journal_vals = {"name": "Compras SCV (upgrade test)", "code": "SCVC", "type": "purchase"}
    if "l10n_latam_use_documents" in env["account.journal"]._fields:
        journal_vals["l10n_latam_use_documents"] = False
    bill_journal = _load(env, "account.journal", "bill_journal", journal_vals)
    warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
    return {
        "company": company, "usd": usd, "ars": company.currency_id, "categ_usd": categ_usd,
        "categ_none": categ_none, "landed_product": landed_product, "vendor": vendor,
        "customer": customer, "bill_journal": bill_journal, "warehouse": warehouse,
        "expense": expense, "stock_journal": categ_usd.with_company(company).property_stock_journal,
    }


def _load(env, model, name, values):
    # Create only: once the flows ran, rewriting (e.g. a journal with posted bills) fails.
    record = env.ref(PREFIX + name, raise_if_not_found=False)
    if record:
        return record
    env[model]._load_records([{"xml_id": PREFIX + name, "values": values, "noupdate": True}])
    return env.ref(PREFIX + name)


def _account(env, company, name, code, label, reconcile):
    return _load(env, "account.account", name, {
        "code": code, "name": label, "account_type": "asset_current", "reconcile": reconcile,
        "company_ids": [(6, 0, company.ids)],
    })


def _tag(env, record, name):
    env["ir.model.data"]._update_xmlids([{"xml_id": PREFIX + name, "record": record, "noupdate": True}])


def _product(env, ctx, key, label, categ="categ_usd", cost_ars=150000.0, cost_usd=100.0):
    product = _load(env, "product.product", key, {
        "name": "SCV %s: %s" % (key.upper(), label), "default_code": "SCV-%s" % key.upper(),
        "type": "consu", "is_storable": True, "categ_id": ctx[categ].id,
    }).with_company(ctx["company"])
    product.with_context(disable_auto_svl=True).write({"standard_price": cost_ars})
    if categ == "categ_usd":
        product.with_context(disable_auto_svl=True).standard_price_in_currency = cost_usd
    return product


# ------------------------------------------------------------------- flows


def _purchase(env, ctx, product, qty, price, currency):
    po = env["purchase.order"].create({
        "partner_id": ctx["vendor"].id, "currency_id": ctx[currency].id, "company_id": ctx["company"].id,
        "order_line": [(0, 0, {"product_id": product.id, "product_qty": qty, "price_unit": price})],
    })
    po.button_confirm()
    return po


def _validate(picking, qty=None):
    for move in picking.move_ids:
        move.quantity = qty if qty is not None else move.product_uom_qty
    picking.move_ids.picked = True
    picking.with_context(skip_backorder=True, picking_ids_not_to_backorder=picking.ids).button_validate()
    return picking


def _receive(po, rate=None):
    picking = po.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
    if rate:
        picking.inverse_currency_rate = rate
    return _validate(picking)


def _landed_cost(env, ctx, picking, amount, rate=None):
    cost = env["stock.landed.cost"].create({
        "picking_ids": [(6, 0, picking.ids)],
        "account_journal_id": ctx["stock_journal"].id,
        "cost_lines": [(0, 0, {
            "product_id": ctx["landed_product"].id, "price_unit": amount, "split_method": "by_quantity",
            "account_id": ctx["expense"].id,
        })],
    })
    if rate:
        cost.inverse_currency_rate = rate
    cost.compute_landed_cost()
    cost.button_validate()
    return cost


def _bill(env, ctx, po, price):
    action = po.action_create_invoice()
    bill = env["account.move"].browse(action["res_id"])
    bill.write({"journal_id": ctx["bill_journal"].id, "invoice_date": fields.Date.today()})
    bill.invoice_line_ids.filtered("product_id").price_unit = price
    bill.action_post()
    return bill


def _return(env, picking, qty):
    wizard = env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking").create({})
    wizard.product_return_moves.quantity = qty
    new_picking = wizard._create_return()
    return _validate(new_picking, qty)


def _stock(env, ctx, product, qty):
    """Bring stock with an inventory adjustment, which leaves its own layer."""
    quant = env["stock.quant"].with_context(inventory_mode=True).search([
        ("product_id", "=", product.id), ("location_id", "=", ctx["warehouse"].lot_stock_id.id),
    ], limit=1)
    if quant:
        quant.inventory_quantity = qty
    else:
        quant = env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": product.id, "location_id": ctx["warehouse"].lot_stock_id.id, "inventory_quantity": qty,
        })
    quant.action_apply_inventory()


def _sale(env, ctx, product, qty, price=250000.0):
    vals = {
        "partner_id": ctx["customer"].id, "company_id": ctx["company"].id,
        "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": qty, "price_unit": price})],
    }
    # Sale exceptions and sale type automations roll the whole transaction back on
    # their own (an unapproved new customer is enough), so neither may apply here.
    fields_ = env["sale.order"]._fields
    if "ignore_exception" in fields_:
        vals["ignore_exception"] = True
    if "type_id" in fields_:
        sale_type = env["sale.order.type"].search([
            ("company_id", "in", [ctx["company"].id, False]),
            ("picking_atomation", "=", "none"), ("invoicing_atomation", "=", "none"),
        ], limit=1)
        if sale_type:
            vals["type_id"] = sale_type.id
    so = env["sale.order"].create(vals)
    so.action_confirm()
    if so.state != "sale":
        raise ValueError("La venta %s no se confirmo (estado %s)" % (so.name, so.state))
    for picking in so.picking_ids.sorted("id"):
        if picking.state not in ("done", "cancel"):
            _validate(picking)
    return so


def _delivery(so):
    return so.picking_ids.filtered(lambda p: p.state == "done" and p.picking_type_code == "outgoing")[:1]


def _outgoing(env, ctx, product, qty):
    picking_type = ctx["warehouse"].out_type_id
    picking = env["stock.picking"].create({
        "picking_type_id": picking_type.id, "location_id": picking_type.default_location_src_id.id,
        "location_dest_id": env.ref("stock.stock_location_customers").id,
        "move_ids": [(0, 0, {
            "name": product.name, "product_id": product.id, "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": env.ref("stock.stock_location_customers").id,
        })],
    })
    picking.action_confirm()
    picking.action_assign()
    return _validate(picking)


def _revaluate(env, ctx, product, added_value, reason):
    env["stock.valuation.layer.revaluation"].with_company(ctx["company"]).create({
        "product_id": product.id, "company_id": ctx["company"].id, "added_value": added_value,
        "reason": reason, "account_id": ctx["expense"].id, "account_journal_id": ctx["stock_journal"].id,
    }).action_validate_revaluation()


# ------------------------------------------------------------------- cases
# Same names as the case map of task 78608. Quantities and prices are small and round
# so each layer can be followed by hand: 10 u at USD 100.


def case_usd_manual_lc_pdiff(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po, rate=PICKING_RATE)
    _landed_cost(env, ctx, picking, 150000.0, rate=LANDED_COST_RATE)
    _landed_cost(env, ctx, picking, 90000.0)
    _bill(env, ctx, po, 110.0)
    _tag(env, po, key + "_po")


def case_usd_manual_lc(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po, rate=PICKING_RATE)
    _landed_cost(env, ctx, picking, 150000.0, rate=LANDED_COST_RATE)
    _tag(env, po, key + "_po")
    _tag(env, picking.move_ids, key + "_move_in")


def case_usd_manual(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po, rate=PICKING_RATE)
    _tag(env, po, key + "_po")
    _tag(env, picking.move_ids, key + "_move_in")


def case_usd_auto_pdiff(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    _receive(po)
    _bill(env, ctx, po, 95.0)
    _tag(env, po, key + "_po")


def case_usd_auto_lc(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    _landed_cost(env, ctx, _receive(po), 120000.0)
    _tag(env, po, key + "_po")


def case_usd_auto(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    _receive(po)
    _tag(env, po, key + "_po")


def case_ars_lc(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 150000.0, "ars")
    _landed_cost(env, ctx, _receive(po), 100000.0, rate=LANDED_COST_RATE)
    _tag(env, po, key + "_po")


def case_ars(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 150000.0, "ars")
    _receive(po)
    _tag(env, po, key + "_po")


def case_purchase_return(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po, rate=PICKING_RATE)
    returned = _return(env, picking, 4)
    _tag(env, po, key + "_po")
    _tag(env, picking.move_ids, key + "_move_in")
    _tag(env, returned.move_ids, key + "_move_return")


def case_sale(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 20)
    so = _sale(env, ctx, product, 5)
    _tag(env, so, key + "_so")
    _tag(env, _delivery(so).move_ids, key + "_move_out")


def case_sale_return(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 20)
    so = _sale(env, ctx, product, 5)
    returned = _return(env, _delivery(so), 2)
    _tag(env, so, key + "_so")
    _tag(env, returned.move_ids, key + "_move_return")


def case_scrap(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 10)
    scrap = env["stock.scrap"].create({
        "product_id": product.id, "scrap_qty": 3, "company_id": ctx["company"].id,
        "location_id": ctx["warehouse"].lot_stock_id.id,
    })
    scrap.action_validate()
    _tag(env, scrap, key + "_scrap")


def case_inventory(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 10)
    _stock(env, ctx, product, 7)


def case_outgoing_no_order(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 10)
    _tag(env, _outgoing(env, ctx, product, 4), key + "_picking")


def case_revaluation(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    _stock(env, ctx, product, 10)
    _revaluate(env, ctx, product, 50000.0, "Revaluacion en mas (upgrade test)")
    _revaluate(env, ctx, product, -20000.0, "Revaluacion en menos (upgrade test)")


def case_usd_manual_lc_after_sale(env, ctx, key, label):
    product = _product(env, ctx, key, label)
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po, rate=PICKING_RATE)
    _sale(env, ctx, product, 4)
    _landed_cost(env, ctx, picking, 150000.0, rate=LANDED_COST_RATE)
    _tag(env, po, key + "_po")


def case_no_valuation_currency(env, ctx, key, label):
    product = _product(env, ctx, key, label, categ="categ_none")
    po = _purchase(env, ctx, product, 10, 100.0, "usd")
    picking = _receive(po)
    _tag(env, po, key + "_po")
    _tag(env, picking.move_ids, key + "_move_in")


# (xmlid key, label, needs sale, flow)
CASES = [
    ("c01", "compra USD, cot. manual, costos en destino y dif. de precio", False, case_usd_manual_lc_pdiff),
    ("c02", "compra USD, cot. manual y costo en destino", False, case_usd_manual_lc),
    ("c03", "compra USD, cot. manual", False, case_usd_manual),
    ("c04", "compra USD, cot. automatica y dif. de precio", False, case_usd_auto_pdiff),
    ("c05", "compra USD, cot. automatica y costo en destino", False, case_usd_auto_lc),
    ("c06", "compra USD, cot. automatica", False, case_usd_auto),
    ("c07", "compra ARS con costo en destino con cot. manual", False, case_ars_lc),
    ("c08", "compra ARS", False, case_ars),
    ("c09", "devolucion de compra", False, case_purchase_return),
    ("c10", "venta", True, case_sale),
    ("c11", "devolucion de venta", True, case_sale_return),
    ("c12", "desecho", False, case_scrap),
    ("c13", "ajuste de inventario en mas y en menos", False, case_inventory),
    ("c14", "salida sin pedido", False, case_outgoing_no_order),
    ("c15", "revalorizacion manual en mas y en menos", False, case_revaluation),
    ("c16", "costo en destino despues de una venta", True, case_usd_manual_lc_after_sale),
    ("c17", "control: producto sin moneda de valuacion", False, case_no_valuation_currency),
]


def _backup_layers(env):
    cr = env.cr
    cr.execute("DROP TABLE IF EXISTS %s" % BACKUP_TABLE)
    cr.execute(
        """
        CREATE TABLE %s AS
            SELECT svl.id AS svl_id,
                   pp.default_code AS case_code,
                   svl.product_id,
                   svl.stock_move_id,
                   svl.stock_valuation_layer_id,
                   svl.stock_landed_cost_id,
                   svl.account_move_id,
                   svl.account_move_line_id,
                   svl.description,
                   svl.quantity,
                   svl.unit_cost,
                   svl.value,
                   svl.remaining_qty,
                   svl.remaining_value,
                   svl.unit_cost_in_currency,
                   svl.value_in_currency,
                   svl.manual_currency_rate,
                   svl.bypass_currency_valuation,
                   svl.create_date
              FROM stock_valuation_layer svl
              JOIN product_product pp ON pp.id = svl.product_id
             WHERE pp.default_code LIKE 'SCV-%%'
        """
        % BACKUP_TABLE
    )
    # Odoo's upgrade flags tables without a primary key.
    cr.execute("ALTER TABLE %s ADD PRIMARY KEY (svl_id)" % BACKUP_TABLE)
    cr.execute("SELECT count(*), count(DISTINCT case_code) FROM %s" % BACKUP_TABLE)
    _logger.info("Backed up %s layers of %s cases in %s", *cr.fetchone(), BACKUP_TABLE)
