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
import post_migration_scripts
# import tempfile
# import urllib2
# import wget

_logger = logging.getLogger(__name__)
# ldir = tempfile.mkdtemp()


# class readable_dir(argparse.Action):
#     def __call__(self, parser, namespace, values, option_string=None):
#         prospective_dir = values
#         if not os.path.isdir(prospective_dir):
#             raise argparse.ArgumentTypeError(
#                 "readable_dir:{0} is not a valid path".format(prospective_dir))
#         if os.access(prospective_dir, os.R_OK):
#             setattr(namespace, self.dest, prospective_dir)
#         else:
#             raise argparse.ArgumentTypeError(
#                 "readable_dir:{0} is not a readable dir".format(
#                     prospective_dir))


# parser = argparse.ArgumentParser(
#     description='Download database, restore it and run migration scripts.')
# parser.add_argument(
#     "-d", "--database_file", dest="database_file",
#     help="Database File (for eg. db.zip)", type=file)
# parser.add_argument(
#     '-s', '--source_db_filestore', dest="source_db_filestore",
#     action=readable_dir)
# parser.add_argument(
#     "-t", "--token", dest="token",
#     help='Migration Request Token', type=str)
# parser.add_argument(
#     "-i", "--migrationId", dest="migrationId",
#     help='Migrarion Request Id', type=str)

# db_name = 'restored_db'


def main():
    logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(filename='myapp.log', level=logging.INFO)
    _logger.info("Starting PRE migration script")

    errors = []
    args = parser.parse_args()

    # get env
    openerp.cli.server.report_configuration()
    openerp.service.server.start(preload=[], stop=True)
    with openerp.api.Environment.manage():
        registry = openerp.modules.registry.Registry(db_name)
        with registry.cursor() as cr:
            uid = openerp.SUPERUSER_ID
            ctx = openerp.api.Environment(
                cr, uid, {})['res.users'].context_get()
            env = openerp.api.Environment(cr, uid, ctx)

            errors += pre_migration_checks()
            errors += pre_migration_scripts()

    return errors


def pre_migration_scripts(env):
    return []


def pre_migration_checks(env):
    return []


if __name__ == '__main__':
    main()
