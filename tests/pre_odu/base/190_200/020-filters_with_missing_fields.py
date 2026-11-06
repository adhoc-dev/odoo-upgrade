import logging

_logger = logging.getLogger(__name__)

# Casos de base/0.0.0/end-220-clean_broken_filters.py, que en los saltos a 20
# limpia los favoritos que usan campos que no existen en la base nueva. Los
# verifica base/tests/expected_200.py.
#
# POR QUE HAY QUE SEMBRAR: ninguna data de prueba trae un favorito roto. En un
# cliente aparecen cuando un modulo se discontinua (stock_voucher, los
# *_multi_store) o un salto saca un campo. Aca el campo roto es uno que no
# existe en ninguna version, asi que el caso no depende de que modulo se vaya.
#
# El dominio y el contexto se escriben por SQL: con el ORM, el favorito no se
# podria guardar con un campo que no existe.

MISSING = "x_upgrade_missing_field"
FILTERS = {
    # En un OR, junto a una condicion valida: se limpia y sigue activo.
    "upgrade_prepare_demo.filter_missing_field_in_or": (
        "Upgrade: missing field in OR",
        "['|', ('name', 'ilike', 'Upgrade'), ('%s', '=', 'a')]" % MISSING,
        "{'group_by': ['%s']}" % MISSING,
        '["%s desc", "name"]' % MISSING,
    ),
    # Solo con el campo roto: no le queda ninguna condicion y se archiva.
    "upgrade_prepare_demo.filter_only_missing_field": (
        "Upgrade: only missing field",
        "[('%s', '=', 'a')]" % MISSING,
        "{}",
        "[]",
    ),
    # Un camino que se corta en el segundo tramo, un group by escrito como texto
    # y una medida del pivote: se limpia todo y sigue activo.
    "upgrade_prepare_demo.filter_missing_field_in_path": (
        "Upgrade: missing field in a path",
        "['|', ('name', 'ilike', 'Upgrade'), ('country_id.%s', '=', 'a')]" % MISSING,
        "{'group_by': '%s', 'pivot_measures': ['%s']}" % (MISSING, MISSING),
        '["%s asc"]' % MISSING,
    ),
    # El campo roto con un operador negado de patron: se detecta y se archiva.
    "upgrade_prepare_demo.filter_missing_field_not_like": (
        "Upgrade: missing field with not =like",
        "[('%s', 'not =like', 'a')]" % MISSING,
        "{}",
        "[]",
    ),
    # La condicion que queda usa "not =ilike": cuenta como condicion real, asi
    # que se limpia y sigue activo.
    "upgrade_prepare_demo.filter_missing_field_and_not_ilike": (
        "Upgrade: missing field and a not =ilike condition",
        "[('%s', '=', 'a'), ('name', 'not =ilike', 'foo')]" % MISSING,
        "{}",
        "[]",
    ),
    # Preservacion: todo existe y no se toca. La lista de valores tiene tres
    # elementos, como una condicion: no se lee como campo. "__count" en el orden
    # es una lista agrupada ordenada por cantidad, no un campo.
    "upgrade_prepare_demo.filter_valid_fields": (
        "Upgrade: valid fields",
        "[('name', 'ilike', 'Upgrade'), ('type', 'in', ['contact', 'invoice', 'delivery'])]",
        "{'group_by': ['country_id']}",
        '["name desc", "-id", "__count desc"]',
    ),
}


def migrate(env):
    for xmlid, (name, domain, context, sort) in FILTERS.items():
        env["ir.filters"]._load_records(
            [{"xml_id": xmlid, "values": {"name": name, "model_id": "res.partner"}, "noupdate": True}]
        )
        env.cr.execute(
            "UPDATE ir_filters SET domain = %s, context = %s, sort = %s, active = true WHERE id = %s",
            (domain, context, sort, env.ref(xmlid).id),
        )
