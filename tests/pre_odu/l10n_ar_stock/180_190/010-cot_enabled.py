import logging

_logger = logging.getLogger(__name__)

# Caso de la COT de ARBA (18 -> 19). En 18 es de nuestro l10n_ar_stock; en 19 pasa a
# l10n_ar_stock_ux, y el pase tiene que conservar el grupo y la secuencia de 18 con el
# xmlid nuevo (scripts/pre_upgrade/180_190/module_changes.json). Lo verifica
# modules/l10n_ar_stock_ux/tests/expected_190.py.
#
# No se crean registros: el grupo y la secuencia ya tienen xmlid estable. Se deja la base
# como la de un cliente que usa la COT:
#   - la casilla "Usar COT de ARBA?" tildada, que Odoo guarda como grupo implicito de
#     "Usuario interno";
#   - la secuencia con un numero que una secuencia nueva no podria tener.
SEQUENCE_NUMBER = 42


def migrate(env):
    group = env.ref("l10n_ar_stock.arba_cot_enabled", raise_if_not_found=False)
    sequence = env.ref("l10n_ar_stock.arba_cot_file_sequence", raise_if_not_found=False)
    if not group or not sequence:
        _logger.info("l10n_ar_stock no esta en esta base — no se siembra nada")
        return
    # Lo mismo que hace res.config.settings al tildar la casilla. Idempotente: (4, id)
    # no duplica el vinculo.
    env.ref("base.group_user").write({"implied_ids": [(4, group.id)]})
    sequence.number_next_actual = SEQUENCE_NUMBER
    _logger.info("COT enabled for internal users and sequence set to %s", SEQUENCE_NUMBER)
