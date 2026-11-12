"""Set Argentina on the Argentine contacts that have neither a country nor a state.

From 19 the sales VAT comes from the fiscal positions, and Odoo applies none to a
contact without country and state (``_get_fiscal_position`` in ``account``): the
invoice is left without the tax. Before 19 the country was not needed, so many
migrated databases have contacts without it (task 79324).

Only the contacts with an ARCA responsibility type that is not a foreign one: in an
Argentine company the ``l10n_ar`` validation skips every auto-applied fiscal position
when the contact has no responsibility type, so the country only matters for the rest.
The foreign ones (codes 8 and 9) are left alone: their country cannot be guessed.

In ``modules/base/0.0.0`` so it also fixes the databases that are already on 19 when
they jump to 20.
"""

import logging

from oba import should_run

_logger = logging.getLogger(__name__)

FIRST_TARGET_VERSION = 19
# Proveedor del Exterior, Cliente del Exterior.
FOREIGN_RESPONSIBILITY_CODES = ("8", "9")


def migrate(cr, version):
    if not should_run(cr, version, FIRST_TARGET_VERSION, modules=["l10n_ar"]):
        return

    cr.execute("SELECT id FROM res_country WHERE code = 'AR'")
    row = cr.fetchone()
    if not row:
        _logger.warning("Country AR not found: contacts without country left as they are")
        return

    cr.execute(
        """
        UPDATE res_partner p
           SET country_id = %s
          FROM l10n_ar_afip_responsibility_type rt
         WHERE rt.id = p.l10n_ar_afip_responsibility_type_id
           AND rt.code NOT IN %s
           AND p.country_id IS NULL
           AND p.state_id IS NULL
        """,
        (row[0], FOREIGN_RESPONSIBILITY_CODES),
    )
    _logger.info("%s contacts without country set to Argentina", cr.rowcount)

    cr.execute(
        """
        SELECT count(*)
          FROM res_partner p
          JOIN l10n_ar_afip_responsibility_type rt ON rt.id = p.l10n_ar_afip_responsibility_type_id
         WHERE rt.code IN %s
           AND p.country_id IS NULL
           AND p.state_id IS NULL
        """,
        (FOREIGN_RESPONSIBILITY_CODES,),
    )
    foreign = cr.fetchone()[0]
    if foreign:
        _logger.info("%s foreign contacts still without country: no fiscal position applies to them", foreign)
