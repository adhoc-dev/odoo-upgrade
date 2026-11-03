import logging

_logger = logging.getLogger(__name__)

# Caso de account_cashbox/20.0.1.0.0/pre-migration.py, que al pasar a 20 vacia
# los usuarios permitidos de las cajas sin "Restringir usuarios". Lo verifica
# account_cashbox/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: la demo del modulo trae la caja sin restriccion
# (pop_config_not_restrict), pero sin usuarios. En 19 los usuarios llegaban a
# esa caja desde el formulario del usuario ("Cajas permitidas"): se carga igual,
# del lado del usuario, para que la caja no recalcule y quede como en los
# clientes.


def migrate(env):
    if "account.cashbox" not in env or "allowed_cashbox_ids" not in env["res.users"]._fields:
        _logger.info("account_cashbox is not installed - not seeding it")
        return
    cashbox = env.ref("account_cashbox.pop_config_not_restrict", raise_if_not_found=False)
    if not cashbox:
        # Sin la demo no hay caso: lo dice el check como ref ausente
        _logger.info("account_cashbox demo data is not in this database - not seeding it")
        return
    users = env.ref("base.user_admin") | env.ref("account_cashbox.user_demo_invoicing")
    for user in users:
        if cashbox not in user.allowed_cashbox_ids:
            user.allowed_cashbox_ids = [(4, cashbox.id)]
    env.flush_all()
