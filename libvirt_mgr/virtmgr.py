#!/usr/bin/env python3

import argparse
import logging
import os

from .migrate import launch_migrate
from .utils import Config

logger = logging.getLogger('libvirt_mgr')


parser = argparse.ArgumentParser(description='Libvirt Manager')

grp_general = parser.add_argument_group(title='General options')
grp_general.add_argument('-c', '--config', default='/etc/libvirt-mgr/config.toml', help='Path to config file')
grp_general.add_argument('--log-level', type=str.upper, choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                         default=os.getenv('LOG_LEVEL', 'INFO'), help='Logging level, env LOG_LEVEL')
grp_general.add_argument('--log-timestamp', action='store_true', help='Log timestamps to console')
grp_general.add_argument('--log-file', help='Path to log file, disables console logging')

subparsers = parser.add_subparsers(title='Commands', required=True)

parser_json = subparsers.add_parser('migrate', help='Migrate VMs')
parser_json.set_defaults(func=launch_migrate)


def setup_logger(args: argparse.Namespace):
    root_logger = logging.getLogger()
    root_logger.setLevel(args.log_level)
    log_fmt = '%(levelname)s:%(name)s: %(message)s'
    logger_fmt_ts = logging.Formatter(f'%(asctime)s:{log_fmt}')
    logger_fmt = logging.Formatter(log_fmt)

    if args.log_file:
        fh = logging.FileHandler(filename=args.log_file, encoding='utf-8', mode='w')
        fh.setLevel(args.log_level)
        fh.setFormatter(logger_fmt_ts)
        root_logger.addHandler(fh)
    else:
        ch = logging.StreamHandler()
        ch.setFormatter(logger_fmt_ts if args.log_timestamp else logger_fmt)
        root_logger.addHandler(ch)


def main():
    args = parser.parse_args()
    setup_logger(args)
    logger.debug('Reading config file: %s', args.config)
    try:
        config = Config.from_file(args.config)
    except Exception as e:
        logger.exception(e)
        raise SystemExit(1)
    args.func(args)


if __name__ == '__main__':
    main()
