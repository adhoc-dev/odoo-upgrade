[![Runbot Status](http://runbot.adhoc.com.a1r/runbot/badge/flat/12/9.0.svg)](http://runbot.adhoc.com.ar/runbot/repo/github-com-ingadhoc-odoo-upgrade-12)
[![Build Status](https://travis-ci.org/ingadhoc/odoo-upgrade.svg?branch=9.0)](https://travis-ci.org/ingadhoc/odoo-upgrade)
[![Coverage Status](https://coveralls.io/repos/ingadhoc/odoo-upgrade/badge.png?branch=9.0)](https://coveralls.io/r/ingadhoc/odoo-upgrade?branch=9.0)
[![Code Climate](https://codeclimate.com/github/ingadhoc/odoo-upgrade/badges/gpa.svg)](https://codeclimate.com/github/ingadhoc/odoo-upgrade)

# ADHOC odoo-upgrade

Ejemplo de uso de script:
python sources/ingadhoc/odoo-upgrade/migrate_script.py  -i xxxxx -t xxxxxxxxxxxxxxxxx -n cliente_mig_id


## TODO:
    * ver que hacemos y que pasó con esos modulos website_sale_note, website_sale_promotion
    * rever migración de retenciones automaticas (por ej. cudnik)
    * Agregar chequeo si quedó diario de reembolso. Agregar chequeos possubt migracion
    * Hacer mig scripts o no (borrar entonces) del website promotion
    * scripts o lque falte de distribution?


## Observaciones:

Tratamos de no usar openupgrade porque:
     * Hace lio con algnas dependencias de los modulos de odoo en v9
     * nos evitamos tener que instalarlo
Tratamos de usar modulos de odoo y no de openupgrade porque:
    * modulos de openupgrade ya tienen scripts de migración y deberíamos sacarlos (o verificar que no se corran por cambio de versión) 
    * para evitar tener que hacer un nuevo -u all luego de actualizar con openupgrade


## Modificaciones incluidas:

#. base: por ahora usamos modulo base de odoo con ciertas modificaciones:
    * con apriori customizado y borrado de vistas.
    * borrmaos content_disposition en import porque el server 
    * Tambien agregamos en base on hook para que establezca todos los modulos que corresponde a instalar, para esto sacamos algo de codigo de openupgrade, lo hacemos así para no necesitar openupgrade (solo necesitmaos openupgradelib)
#. partner_identification: lo sumamos porque tiene nuestros scripts de migracion
#. sale_order_type: sin scripts de migracion ya que el que tiene esta preparado para migrar version anterior de v9 y da error si viene bien de v8

TODO:
* correr scripts de postmigracion automaticamente
* evitar update de todo odoo, es decir, de alguna manera hacer que se marque por auto instalar lo que falta sin necesidad del -u all, en realidad esto ya practicamente anda, simplemnte habria que activar el update all del hook y llamar a los scripts de pre-migracion, ahora bien, para que queremos eso?

ADHOC Odoo odoo-upgrade Modules

[//]: # (addons)
This part will be replaced when running the oca-gen-addons-table script from OCA/maintainer-tools.
[//]: # (end addons)

----

<img alt="ADHOC" src="http://fotos.subefotos.com/83fed853c1e15a8023b86b2b22d6145bo.png" />
**Adhoc SA** - www.adhoc.com.ar
