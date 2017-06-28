# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp.service import db
from openerp.tools import config
import argparse
import base64
import logging
import os
# import urllib2
# import wget

_logger = logging.getLogger(__name__)

# print 'Hello'
parser = argparse.ArgumentParser(
    description='Download database, restore it and run migration scripts.')
# parser.add_argument(
#     'clone_path', metavar='--clone_path', type=str, help='Clone Path')
parser.add_argument(
    "-f", "--database_file", dest="database_file",
    help="Database File (for eg. db.zip)", type=file)
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


def main():
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(filename='myapp.log', level=logging.INFO)
    _logger.info("Startint migration script")
    args = parser.parse_args()
    database_file = args.database_file

    # TODO: lo hacemos opcional?
    _logger.info("Overwritting config file")
    config['update'] = {'all': 1}

    # config['addons_path'] = (
    #     'sources/odoo/enterprise/,sources/odoo/odoo/addons/,'
    #     'sources/odoo/odoo/openerp/addons/')
    # config['server_wide_modules'] = '--load=web_kanban,web'

    _logger.info("Reading file for restore")
    if not database_file:
        # url = args.database_file_url
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
    else:
        data_b64 = base64.encodestring(database_file.read())

    _logger.info("Calling db restore")
    db.exp_restore('restored_db', data_b64, copy=False)
    _logger.info("Finish restoring database")


if __name__ == '__main__':
    main()
