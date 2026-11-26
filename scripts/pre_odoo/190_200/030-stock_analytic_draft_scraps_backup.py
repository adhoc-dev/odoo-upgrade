import logging

from oba import create_backup, should_back_up

_logger = logging.getLogger(__name__)

# Read by modules/stock_analytic/20.0.1.0.0/post-migration.py, on the other side of the pass.
#
# In 19 stock_analytic keeps the analytic distribution of a scrap on the scrap itself, and
# only copies it to the stock move when the scrap is validated. Odoo 20 removes stock.scrap
# as a model of its own (a scrap is a flagged stock move), so the distribution of a scrap
# still in draft has nowhere to go and is gone by the time our -u runs. Validated scraps
# are fine: their distribution already travels on the move.
#
# Nothing is restored: the customer note lists these scraps so the customer loads the
# distribution again before validating them. The texts are resolved here, on the old
# database, so the note shows what the customer saw in 19.
BACKUP_TABLE = "stock_scrap_draft_analytic_bu"
FIRST_TARGET_VERSION = 20

# Translated names are jsonb: the language of the scrap's company first, then en_US, which
# Odoo always writes, then any value for a record that only ever had another language.
NAME = (
    "COALESCE({t}.name ->> rp.lang, {t}.name ->> 'en_US', "
    "(SELECT value FROM jsonb_each_text({t}.name) LIMIT 1))"
)

# One entry per line of the distribution. A key is an account id, or several joined by a
# comma when the line combines plans; its value is the percentage. 100 % goes without the
# number, which is the usual case and reads cleaner.
ANALYTIC_ACCOUNTS = """
    (SELECT string_agg(
                (SELECT string_agg({account_name}, ' / ' ORDER BY k.ord)
                   FROM unnest(string_to_array(d.key, ',')) WITH ORDINALITY AS k(account_id, ord)
                   JOIN account_analytic_account a ON a.id::text = k.account_id)
                || CASE WHEN d.value::numeric = 100 THEN ''
                        ELSE ' (' || replace(rtrim(rtrim(round(d.value::numeric, 2)::text, '0'), '.'), '.', ',')
                             || ' %)'
                   END,
                ', ' ORDER BY d.key)
       FROM jsonb_each_text(s.analytic_distribution) AS d)
""".format(account_name=NAME.format(t="a"))

QUERY = """
    SELECT s.id,
           to_char(s.create_date, 'YYYY-MM-DD') AS fecha,
           CASE WHEN COALESCE(pp.default_code, '') != '' THEN '[' || pp.default_code || '] ' ELSE '' END
           || {product_name} AS producto,
           s.scrap_qty AS cantidad,
           {uom_name} AS unidad,
           {accounts} AS cuenta_analitica
      FROM stock_scrap s
      JOIN product_product pp ON pp.id = s.product_id
      JOIN product_template pt ON pt.id = pp.product_tmpl_id
      JOIN uom_uom u ON u.id = s.product_uom_id
      JOIN res_company c ON c.id = s.company_id
      JOIN res_partner rp ON rp.id = c.partner_id
     WHERE s.state = 'draft'
       AND s.analytic_distribution IS NOT NULL
       AND s.analytic_distribution != '{{}}'::jsonb
""".format(
    product_name=NAME.format(t="pt"),
    uom_name=NAME.format(t="u"),
    accounts=ANALYTIC_ACCOUNTS,
)


def migrate(cr, version):
    """Back up the draft scraps that have an analytic distribution, before Odoo drops them.

    Backup only: nothing of the old database changes.

    No `odoo.upgrade.util` nor `odoo.tools.SQL` on purpose: this runs on the old database,
    with the Odoo of the source version.
    """
    # Drops BACKUP_TABLE before any condition: a table of a previous run cannot travel in a
    # request this script does not apply to. The platform does not filter by module: the
    # module is checked here.
    if not should_back_up(
        cr,
        BACKUP_TABLE,
        FIRST_TARGET_VERSION,
        FIRST_TARGET_VERSION,
        modules=["stock_analytic"],
    ):
        return

    # The module can be installed while the -u that adds the column has not run yet. With
    # no column there is nothing to back up, and the reader warns that nobody looked.
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        " WHERE table_name = 'stock_scrap' AND column_name = 'analytic_distribution'"
    )
    if not cr.fetchone():
        _logger.warning("stock_scrap.analytic_distribution does not exist: nothing backed up")
        return

    _logger.info("Backing up draft scraps with analytic distribution into %s", BACKUP_TABLE)
    rows = create_backup(cr, BACKUP_TABLE, QUERY)
    _logger.info("%s draft scraps backed up", rows)
