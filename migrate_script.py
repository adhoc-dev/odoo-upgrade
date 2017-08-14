# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp.service import db
from openerp.tools import config
import openerp
import argparse
import base64
import logging
import os
import shutil
import subprocess
import post_migration_scripts
# import tempfile
# import urllib2
# import wget

_logger = logging.getLogger(__name__)
# ldir = tempfile.mkdtemp()

# import logging
# logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)
# logger = logging.getLogger('myapp')
# hdlr = logging.FileHandler('/var/tmp/myapp.log')
# formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
# hdlr.setFormatter(formatter)
# logger.addHandler(hdlr)
# logger.setLevel(logging.WARNING)


class readable_dir(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir = values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentTypeError(
                "readable_dir:{0} is not a valid path".format(prospective_dir))
        if os.access(prospective_dir, os.R_OK):
            setattr(namespace, self.dest, prospective_dir)
        else:
            raise argparse.ArgumentTypeError(
                "readable_dir:{0} is not a readable dir".format(
                    prospective_dir))


parser = argparse.ArgumentParser(
    description='Download database, restore it and run migration scripts.')
parser.add_argument(
    "-d", "--database_file", dest="database_file",
    help="Database File (for eg. db.zip)", type=file)
parser.add_argument(
    '-s', '--source_db_filestore', dest="source_db_filestore",
    action=readable_dir)
parser.add_argument(
    "-t", "--token", dest="token",
    help='Migration Request Token', type=str)
# parser.add_argument(
#     "-n", "--db_name", dest="db_name",
#     help='Restored Database name', type=str)
parser.add_argument(
    "-a", "--account_name", dest="account_name",
    help='Account name', type=str)
parser.add_argument(
    "-i", "--migrationId", dest="migrationId",
    help='Migrarion Request Id', type=str)

# restore backups parameters
parser.add_argument(
    "-x", "--aws_s3_accessid", dest="aws_s3_accessid", type=str)
parser.add_argument(
    "-y", "--aws_s3_accesskey", dest="aws_s3_accesskey", type=str)
parser.add_argument(
    "-z", "--aws_s3_bucket", dest="aws_s3_bucket", type=str)


# parser.parse_args()
# db_name = parser.parse_args().db_name or 'restored_db'
account_name = parser.parse_args().account_name
migrationId = parser.parse_args().migrationId
db_name = migrationId and "%s_%s" % (account_name, migrationId) or account_name
log_file = 'odoo-upgrade.log'


def main():
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(filename='myapp.log', level=logging.INFO)
    _logger.info("Starting migration script")

    errors = []
    args = parser.parse_args()

    if db_name in openerp.service.db.list_dbs(True):
        _logger.warning('Database "%s" already existis' % db_name)
    else:
        database_file = args.database_file
        if not database_file:
            data_b64 = download_database()
        else:
            data_b64 = base64.encodestring(database_file.read())

        # como copy tree solo permite
        source_db_filestore = args.source_db_filestore
        if source_db_filestore:
            copy_source_filestore(source_db_filestore)
        else:
            _logger.warning("Restore called without source_db_filestore")

        restoring_database(data_b64)

    _logger.info("Upgrading with configuration\n%s" % config.options)

    update_database()

    if not test_update_ok():
        return False

    _logger.info('Odoo update terminada')

    errors += run_script(args)

    # NO ME ANDUVO
    # # al final esto lo hacemos desde el saas upgrade
    # # purgamos bd
    errors += purge_database(args)

    if errors:
        _logger.error(
            'Actualización terminada con los siguientes errores:\n* %s' % (
                '\n\n* '.join(errors)))
    _logger.info('Actualización terminada sin ningún error.')

    aws_s3_accessid = args.aws_s3_accessid
    aws_s3_accesskey = args.aws_s3_accesskey
    aws_s3_bucket = args.aws_s3_bucket
    if aws_s3_accessid and aws_s3_accesskey and aws_s3_bucket:
        upload_backup(
            aws_s3_accessid, aws_s3_accesskey, aws_s3_bucket, account_name)


def upload_backup(
        aws_s3_accessid, aws_s3_accesskey, aws_s3_bucket, account_name):
    _logger.info('Making backup to %s' % aws_s3_bucket)
    config = openerp.tools.config
    config['saas_client.aws_s3_accessid'] = aws_s3_accessid
    config['saas_client.aws_s3_accesskey'] = aws_s3_accesskey
    config['saas_client.aws_s3_bucket'] = aws_s3_bucket
    # no se porque este parametro no me lo lee
    # config['saas_client.aws_s3_backup_enable'] = True
    config['saas_client.account_name'] = account_name
    # openerp.cli.server.report_configuration()
    # openerp.service.server.start(preload=[], stop=True)
    with openerp.api.Environment.manage():
        registry = openerp.modules.registry.RegistryManager.get(db_name)
        # con esto trato de evitar un error que me dio
        openerp.modules.registry.RegistryManager.signal_registry_change(
            db_name)
        with registry.cursor() as cr:
            uid = openerp.SUPERUSER_ID
            ctx = openerp.api.Environment(
                cr, uid, {})['res.users'].context_get()
            env = openerp.api.Environment(cr, uid, ctx)
            # lo steamos en el config porque si los borramos en realidad
            # ya estan en el backup
            set_param = env['ir.config_parameter'].set_param

            set_param('saas_client.aws_s3_backup_enable', True)
            # set_param('saas_client.aws_s3_accessid', aws_s3_accessid)
            # set_param('saas_client.aws_s3_accesskey', aws_s3_accesskey)
            # set_param('saas_client.aws_s3_bucket', aws_s3_bucket)
            # set_param('saas_client.account_name', account_name)

            env['saas_client.dashboard'].backup_database()

            # env['ir.config_parameter'].search(
            #     [('key', '=', 'saas_client.aws_s3_accessid')],
            #     limit=1).unlink()
            # env['ir.config_parameter'].search(
            #     [('key', '=', 'saas_client.aws_s3_accesskey')],
            #     limit=1).unlink()


def test_update_ok():
    """
    Por ahora consideramos que odoo actualizo bien si en el log se llega a la
    parte de computing left and...
    TODO otra alternativa es chequear si existe la palabra critical o error
    aparecen en el log, en ese caso, deberíamos generar un nuevo archivo de
    log para cada base y borrarlo antes de arrancar, para que no se confunda
    con errores de otros arranques
    """
    # log_lines = subprocess.check_output(['cat', log_file])
    log_lines = subprocess.check_output(['tail', '-10', log_file])
    # al final chequeamos si hay cirticial o error solamente
    # log_lines = subprocess.check_output(['tail', '-10', log_file])
    # if log_lines.find('CRITICAL', 'ERROR'):
    if log_lines.find(
            "Computing parent left and right for table ir_ui_menu") == -1:
        _logger.error(
            'Abortando. Parece que hubo algun error en la actualización de '
            'odoo. Por favor revise las líneas con "CRITICAL" o "ERROR" en '
            '"%s" e intente nuevamente' % (
                log_file))
        return False
    return True


def purge_database(args):
    """
    Lo hacemos en otro env que el run scripts porque si no tenemos un error
    que no se arregla ni con commit
    Lo ideal seria llevar todo el with a una funcion de afuera
    """
    errors = []
    suffixs = [
        'module', 'model', 'column', 'table', 'menu', 'data', 'property']

    errors = []
    # setamos log file (no me anduvo)
    # config['logfile'] = log_file
    # openerp.cli.server.report_configuration()
    # openerp.service.server.start(preload=[], stop=True)
    with openerp.api.Environment.manage():
        registry = openerp.modules.registry.RegistryManager.get(db_name)
        with registry.cursor() as cr:
            uid = openerp.SUPERUSER_ID
            ctx = openerp.api.Environment(
                cr, uid, {})['res.users'].context_get()
            env = openerp.api.Environment(cr, uid, ctx)

            # purgamos bd
            for suffix in suffixs:
                _logger.info('Purging model %s' % suffix)
                try:
                    env['cleanup.purge.wizard.%s' % suffix].create(
                        {}).purge_all()
                except Exception, e:
                    errors.append('Error al purgar %s:\n%s' % (suffix, e))

                # esta tabla tiene nombre totalmente distinto
                _logger.info('Purging create_indexes')
                try:
                    env['cleanup.create_indexes.wizard'].create(
                        {}).purge_all()
                except Exception, e:
                    errors.append('Error al purgar %s:\n%s' % (suffix, e))
    return errors


def run_script(args):
    # openerp.tools.config.parse_config(args)
    errors = []
    # setamos log file (no me anduvo)
    # config['logfile'] = log_file
    # openerp.service.server.start(preload=[], stop=True)
    with openerp.api.Environment.manage():
        registry = openerp.modules.registry.RegistryManager.get(db_name)
        with registry.cursor() as cr:
            uid = openerp.SUPERUSER_ID
            ctx = openerp.api.Environment(
                cr, uid, {})['res.users'].context_get()
            env = openerp.api.Environment(cr, uid, ctx)

            # corremos post scripts
            errors += post_migration_scripts.run_scripts(env)
    return errors


def copy_source_filestore(source_db_filestore):
    _logger.info("Copy source filestore from %s" % (source_db_filestore))
    filestore = openerp.tools.config.filestore(db_name)
    shutil.copytree(source_db_filestore, filestore)


def update_database():
    _logger.info("Startint database update")
    # actualizamos instalando saas client por las sudas
    os.system(
        # "odoo.py --workers=0 --stop-after-init -d %s "
        "odoo.py --workers=0 --stop-after-init -d %s -u all "
        "-i saas_client --without-demo=True --no-xmlrpc --logfile=%s" % (
            db_name, log_file))


def download_database():
    _logger.info("Reading file for restore")
    # url = args.database_file_url
    args = parser.parse_args()
    token = args.token
    # if not url:
    if not migrationId or not token:
        _logger.info(
            "If not database file send, then migration token and id are "
            "mandatory")
        return False
    url = (
        "https://upgrade.odoo.com/database/eu1/%s/%s/upgraded/archive" %
        (migrationId, token))
    _logger.info("Downloading file from %s" % url)
    # 'download.zip'
    file_name = "%s.zip" % db_name
    os.system("wget --continue -O %s %s" % (file_name, url))

    # metodo traido de db tools
    f = file(file_name, 'r')
    data_b64 = base64.encodestring(f.read())
    f.close()
    return data_b64


def restoring_database(data_b64):

    # TODO: lo hacemos opcional?
    _logger.info("Overwritting config file")
    # config['update'] = {'all': 1}

    addons_path = config['addons_path']
    server_wide_modules = config['server_wide_modules']
    config['addons_path'] = (
        'sources/odoo/enterprise/,sources/odoo/odoo/addons/,'
        'sources/odoo/odoo/openerp/addons/')
    config['server_wide_modules'] = '--load=web_kanban,web'

    _logger.info("Restoring with configuration\n%s" % config.options)

    _logger.info("Calling db restore")
    db.exp_restore(db_name, data_b64, copy=False)
    _logger.info("Finish restoring database")

    # restore defualt config
    config['addons_path'] = addons_path
    config['server_wide_modules'] = server_wide_modules


if __name__ == '__main__':
    # el KeyboardInterrupt no anda como espero pero tampoco molesta por ahora
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        _logger.warning('Interrumpido por teclado')
