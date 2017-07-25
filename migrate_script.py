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
# import tempfile
# import urllib2
# import wget

_logger = logging.getLogger(__name__)
# ldir = tempfile.mkdtemp()


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
# parser.add_argument(
#     'clone_path', metavar='--clone_path', type=str, help='Clone Path')
parser.add_argument(
    "-d", "--database_file", dest="database_file",
    help="Database File (for eg. db.zip)", type=file)
parser.add_argument(
    '-s', '--source_db_filestore', dest="source_db_filestore",
    action=readable_dir)
# parser.add_argument(
#     "-u", "--database_file_url", dest="database_file_url",
#     help='Database File Url between ""', type=str)
parser.add_argument(
    "-t", "--token", dest="token",
    help='Migration Request Token', type=str)
parser.add_argument(
    "-i", "--migrationId", dest="migrationId",
    help='Migrarion Request Id', type=str)
# parser.add_argument(
#     "-c", "--config", dest="config", help="specify alternate config file")

db_name = 'restored_db'


def main():
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(filename='myapp.log', level=logging.INFO)
    _logger.info("Startint migration script")

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

    update_database()


def copy_source_filestore(source_db_filestore):
    _logger.info("Copy source filestore from %s" % (source_db_filestore))
    filestore = openerp.tools.config.filestore('restored_db')
    shutil.copytree(source_db_filestore, filestore)


def update_database():
    _logger.info("Startint database update")
    os.system("odoo.py --workers=0 --stop-after-init -u all -d %s" % db_name)


def download_database():
    _logger.info("Reading file for restore")
    # url = args.database_file_url
    args = parser.parse_args()
    token = args.token
    migrationId = args.migrationId
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
    file_name = 'download.zip'
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

    _logger.info("Working with configuration\n%s" % config.options)

    addons_path = config['addons_path']
    server_wide_modules = config['server_wide_modules']
    config['addons_path'] = (
        'sources/odoo/enterprise/,sources/odoo/odoo/addons/,'
        'sources/odoo/odoo/openerp/addons/')
    config['server_wide_modules'] = '--load=web_kanban,web'

    _logger.info("Calling db restore")
    db.exp_restore(db_name, data_b64, copy=False)
    _logger.info("Finish restoring database")

    # restore defualt config
    config['addons_path'] = addons_path
    config['server_wide_modules'] = server_wide_modules


if __name__ == '__main__':
    main()
