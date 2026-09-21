# Test declarativo de la migracion STORE TO BRANCH de base/19.0.0.0.
#
# La transformacion: en 18 una sola company con varios res.store; en 19 los
# stores no existen mas y cada uno pasa a ser una branch (res.company colgada de
# la parent). end-migration.py resuelve store -> company
# (get_store_to_company_mapping) y despues reescribe el company_id de todo lo
# que tenia store_id (migrate_store_fields_to_company).
#
#   store con company homonima ya existente  -> los registros de ese store van
#                                               a ESA company
#   store sin company homonima               -> se crea una branch nueva
#   registro sin store                       -> no se toca (preservacion)
#
# QUE NO CUBRE ESTE ARCHIVO, y por que. La rama mas comun en produccion —el
# store que NO matchea ninguna company y termina en una branch que la migracion
# CREA— queda fuera del carril declarativo: esa company nace sin xmlid y el
# check resuelve los ref contra ir_model_data, asi que no hay forma de
# apuntarle. Por eso el caso positivo de aca entra por la otra rama, la de
# company homonima preexistente, que es la unica cuyo destino se puede
# referenciar (la siembra la crea con xmlid en
# testing_pre_odu/base/180_190/030-store_to_branch_cases.py).
#
# DE QUE DEPENDE EL ROJO, que es lo que este carril no puede declarar. El
# assert de res.company ejercita la deteccion de la parent company por su
# camino de FALLBACK: la primera query de get_store_to_company_mapping
# (sale_order + stock_warehouse) no resuelve en la base canonica, y recien por
# eso la parent sale de la company del store raiz. Si esa base llegara a tener
# sale orders con warehouse en una sola company raiz, esa primera query pasa a
# devolver una fila, el fallback deja de correr y los seis asserts de aca
# siguen en VERDE sin haber tocado el codigo que verifican. El verde prueba el
# resultado, no el camino: al tocar la data canonica hay que rehacer el rojo
# (revertir el fix y ver el fail) para saber que el assert sigue discriminando.
#
# Solo se declara el estado esperado DESPUES del -u (ADR 0007): la base que
# recibimos se da por buena.

EXPECTED = {
    "account.journal": {
        # Rama "store -> company homonima": parte de company_id = Muebleria US
        # (la main company) y store_id = el store sembrado "Sucursal
        # Declarativa". migrate_store_fields_to_company tiene que dejarlo en la
        # company del mismo nombre. Si queda en la main company, el UPDATE por
        # store no corrio (store_mapping vacio, o el modelo quedo afuera del
        # barrido de ir.model.fields); si queda en cualquier otra, el store se
        # resolvio a la company equivocada, que es el bug que mas caro sale:
        # los diarios de una sucursal facturando desde otra.
        ref("upgrade_prepare_demo.journal_store_to_branch"): {
            "company_id": ref("upgrade_prepare_demo.company_store_to_branch"),
        },
        # Rama de preservacion: mismo modelo, misma company de partida, pero
        # sin store. Tiene que quedarse en la main company. Verifica que el
        # UPDATE filtre por store_id y no arrastre a toda la tabla — el falso
        # positivo mas probable de una migracion que mueve company_id por SQL.
        ref("upgrade_prepare_demo.journal_no_store"): {
            "company_id": ref("base.main_company"),
        },
    },
    "stock.warehouse": {
        # Preservacion en el otro modelo con store_id propio: el almacen de la
        # main company nunca tuvo store, asi que se queda donde esta. En la base
        # canonica conviven con el dos almacenes que SI tienen store (Rosario y
        # Bs As) y que se van a sus branches; esto verifica que ese movimiento
        # no se lleve puesto al que no corresponde.
        ref("stock.warehouse0"): {
            "company_id": ref("base.main_company"),
        },
    },
    "stock.location": {
        # Preservacion de migrate_warehouse_stock_to_company: esa funcion
        # realinea TODO el subarbol de ubicaciones de cada almacen con la
        # company del almacen, por SQL y sin filtrar por store. WH/Stock cuelga
        # del almacen de la main company, que no migra, asi que tiene que
        # seguir ahi. Si aparece en otra company, el realineo agarro el arbol
        # equivocado y se llevo el stock de la parent a una sucursal.
        ref("stock.stock_location_stock"): {
            "company_id": ref("base.main_company"),
        },
    },
    "res.company": {
        # La rama que ARMA la jerarquia, que es el punto de toda la migracion:
        # no alcanza con que los registros del store cambien de company, la
        # company tiene que quedar colgada de la parent. La parent sale del
        # store raiz ("Your Company Stores", company_id = la main company), asi
        # que la sucursal del store sembrado tiene que terminar como branch de
        # base.main_company. Si aparece vacio, el store matcheo la company por
        # nombre pero nadie le seteo el parent_id y quedo como una company
        # independiente mas; si aparece OTRA company, la deteccion de la parent
        # eligio mal la raiz del arbol, y ahi se va todo lo que cuelga de la
        # raiz: cierre fiscal, talonarios y el shared_to_branches de los
        # diarios.
        ref("upgrade_prepare_demo.company_store_to_branch"): {
            "parent_id": ref("base.main_company"),
        },
        # Preservacion del otro lado: la parent es la raiz del arbol y tiene
        # que seguir siendolo. El matcheo store -> company es POR NOMBRE y
        # cuelga de la parent todo lo que matchea; si alguna vez matcheara la
        # propia parent, esto lo muestra antes que cualquier sintoma funcional
        # (una raiz convertida en branch pierde su cierre fiscal).
        ref("base.main_company"): {
            "parent_id": None,
        },
    },
}
