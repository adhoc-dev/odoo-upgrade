import logging

_logger = logging.getLogger(__name__)

TABLE_FP = "account_fiscal_position"
TABLE_AR_TAX = "account_fiscal_position_l10n_ar_tax"


def _get_columns(cr, table, exclude=None):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        [table],
    )
    cols = [row[0] for row in cr.fetchall()]
    if exclude:
        cols = [c for c in cols if c not in exclude]
    return cols


def _duplicate_fiscal_position(cr, fp_id):
    """Copy an account_fiscal_position row (name unchanged). Returns the new id."""
    cols = _get_columns(cr, TABLE_FP, exclude=["id"])
    quoted_cols = ", ".join(f'"{c}"' for c in cols)
    select_str = ", ".join(f'"{c}"' for c in cols)
    cr.execute(
        f"""
        INSERT INTO {TABLE_FP} (id, {quoted_cols})
        SELECT nextval('{TABLE_FP}_id_seq'), {select_str}
        FROM {TABLE_FP}
        WHERE id = %s
        RETURNING id
        """,
        [fp_id],
    )
    return cr.fetchone()[0]


def _get_name_col_type(cr):
    """Return 'jsonb' if the name column is JSONB (translate=True in v17+), else 'varchar'."""
    cr.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = 'name'
        """,
        [TABLE_FP],
    )
    row = cr.fetchone()
    if row and "json" in row[0].lower():
        return "jsonb"
    return "varchar"


def _append_name_suffix(cr, fp_id, suffix, name_type):
    """Append suffix to the name of fp_id. Handles both JSONB (v17+) and VARCHAR."""
    if name_type == "jsonb":
        cr.execute(
            f"""
            UPDATE {TABLE_FP}
            SET name = (
                SELECT jsonb_object_agg(key, value || %s)
                FROM jsonb_each_text(name)
            )
            WHERE id = %s
            """,
            [suffix, fp_id],
        )
    else:
        cr.execute(
            f"UPDATE {TABLE_FP} SET name = name || %s WHERE id = %s",
            [suffix, fp_id],
        )


def _copy_ar_tax_lines(cr, source_fp_id, target_fp_id, tax_type):
    """Copy l10n_ar_tax lines of a given tax_type from source to target fiscal position."""
    if not _table_exists(cr, TABLE_AR_TAX):
        return
    cols = _get_columns(cr, TABLE_AR_TAX, exclude=["id"])
    if not cols:
        return
    quoted_cols = ", ".join(f'"{c}"' for c in cols)
    select_exprs = []
    params = []
    for c in cols:
        if c == "fiscal_position_id":
            select_exprs.append("%s")
            params.append(target_fp_id)
        else:
            select_exprs.append(f'"{c}"')
    select_str = ", ".join(select_exprs)
    params.extend([source_fp_id, tax_type])
    cr.execute(
        f"""
        INSERT INTO {TABLE_AR_TAX} (id, {quoted_cols})
        SELECT nextval('{TABLE_AR_TAX}_id_seq'), {select_str}
        FROM {TABLE_AR_TAX}
        WHERE fiscal_position_id = %s AND tax_type = %s
        """,
        params,
    )


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        [table],
    )
    return bool(cr.fetchone())


def _find_conflicting_fiscal_positions(cr):
    """Return ids of fiscal positions that still have both perception and withholding lines.

    The WHERE clause is the idempotency guard: once split, the original only has perception lines
    and the new copy only has withholding lines, so neither qualifies on a re-run.
    """
    if not _table_exists(cr, TABLE_AR_TAX):
        return []
    cr.execute(
        f"""
        SELECT DISTINCT fp.id
        FROM {TABLE_FP} fp
        WHERE EXISTS (
            SELECT 1 FROM {TABLE_AR_TAX} t
            WHERE t.fiscal_position_id = fp.id AND t.tax_type = 'perception'
        )
        AND EXISTS (
            SELECT 1 FROM {TABLE_AR_TAX} t
            WHERE t.fiscal_position_id = fp.id AND t.tax_type = 'withholding'
        )
        ORDER BY fp.id
        """
    )
    return [row[0] for row in cr.fetchall()]


def migrate(cr, version):
    conflicting = _find_conflicting_fiscal_positions(cr)

    if not conflicting:
        _logger.info("l10n_ar_tax 19.0.0.0: no mixed fiscal positions found, skipping split")
        return

    _logger.info(
        "l10n_ar_tax 19.0.0.0: splitting %d mixed fiscal position(s) (perception + withholding)",
        len(conflicting),
    )

    name_type = _get_name_col_type(cr)
    _logger.info("l10n_ar_tax 19.0.0.0: 'name' column type: %s", name_type)

    for fp_id in conflicting:
        # 1. Duplicate FP header (name unchanged at this point)
        new_fp_id = _duplicate_fiscal_position(cr, fp_id)

        # 2. Rename copy → "- Retenciones"
        _append_name_suffix(cr, new_fp_id, " - Retenciones", name_type)

        # 3. Copy withholding lines to the new position
        _copy_ar_tax_lines(cr, fp_id, new_fp_id, "withholding")

        # 4. Rename original → "- Percepciones" and remove its withholding lines
        _append_name_suffix(cr, fp_id, " - Percepciones", name_type)
        cr.execute(
            f"DELETE FROM {TABLE_AR_TAX} WHERE fiscal_position_id = %s AND tax_type = 'withholding'",
            [fp_id],
        )

        _logger.info(
            "  split OK: fp_id=%s → Percepciones (id=%s) + Retenciones (id=%s)",
            fp_id,
            fp_id,
            new_fp_id,
        )
