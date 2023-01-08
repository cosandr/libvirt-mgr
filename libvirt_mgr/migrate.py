import argparse
import logging
import time
from typing import List, Optional, Union

import libvirt

from .utils import Config, HostConfig


logger = logging.getLogger(__name__)


def launch_migrate(args: argparse.Namespace, config: Config):
    # Validate arguments vs config
    src_host: HostConfig = config.hosts.get(args.src_host)
    if not src_host:
        raise Exception(f'Source host "{args.src_host}" not found in configuration')
    dst_host: Optional[HostConfig] = None
    if args.dst_group:
        exclude_dst_hosts = [src_host.name]
        dst_host = get_host_from_group(config, args.dst_group, exclude_dst_hosts)
    else:
        dst_host = config.hosts.get(args.dst_host)
        if not dst_host:
            raise Exception(f'Destination host "{args.dst_host}" not found in configuration')
        elif src_host == dst_host:
            raise Exception('Source and destination host cannot be the same')

    # Connect to source hypervisor
    try:
        src_conn = libvirt.open(src_host.uri)
    except libvirt.libvirtError:
        logger.critical('Cannot connect to source hypervisor "%s"', src_host.name)
        raise

    dom_list: List[libvirt.virDomain] = []
    if args.all:
        id_list = src_conn.listDomainsID()
        if not id_list:
            logger.info('Source host "%s" has no active domains.', src_host.name)
            return
        for dom_id in id_list:
            dom = get_domain(src_conn, dom_id)
            if dom is None:
                logger.warning('Cannot find domain with ID "%d" on host "%s"', dom_id, src_host.name)
                continue
            dom_list.append(dom)
    else:
        dom = get_domain(src_conn, args.name)
        if dom is None:
            logger.error('Cannot find domain with name "%s" on host "%s"', args.name, src_host.name)
            raise SystemExit(1)
        dom_list.append(dom)

    if not dom_list:
        logger.info('No domains found on host "%s"', src_host.name)
        return

    # Connect to destination hypervisor
    try:
        dst_conn = libvirt.open(dst_host.uri)
    except libvirt.libvirtError:
        logger.critical('Cannot connect to destination hypervisor "%s"', dst_host.name)
        raise

    # Determine migration flags
    if src_host.group == dst_host.group:
        flags = config.groups[src_host.group].same_group_flags
        logger.info('Using flags for migration within the same group')
    else:
        flags = config.groups[src_host.group].different_group_flags
        logger.info('Using flags for migration between different groups')
    logger.debug(f'Migration flags {flags:b}')
    migrate_domains(
        src_conn=src_conn,
        dst_conn=dst_conn,
        domains=dom_list,
        flags=flags,
        auto_stop=not args.no_stop,
        auto_start=not args.no_start,
    )
    src_conn.close()
    logger.debug('Closed source connection')
    dst_conn.close()
    logger.debug('Closed destination connection')


def get_host_from_group(config: Config, group_name: str, exclude: Optional[List[str]] = None) -> HostConfig:
    raise NotImplementedError


def get_domain(conn: libvirt.virConnect, dom: Union[int, str]) -> Optional[libvirt.virDomain]:
    try:
        if isinstance(dom, int):
            return conn.lookupByID(dom)
        else:
            return conn.lookupByName(dom)
    except libvirt.libvirtError as e:
        logger.debug(str(e))
        return None


def migrate_domains(
    src_conn: libvirt.virConnect,
    dst_conn: libvirt.virConnect,
    domains: List[libvirt.virDomain],
    flags: int,
    auto_stop: bool = True,
    auto_start: bool = True,
):
    live_migration = flags & libvirt.VIR_MIGRATE_LIVE
    offline_migration = flags & libvirt.VIR_MIGRATE_OFFLINE
    for dom in domains:
        logger.info('Migrating "%s"', dom.name())
        if not dom.isActive() and live_migration:
            logger.warning('"%s" is offline, cannot live migrate', dom.name())
            continue
        if dom.isActive() and offline_migration:
            if auto_stop:
                logger.warning('"%s" is running, shutting down before offline migration', dom.name())
                dom.shutdown()
                logger.info('Waiting for "%s" to shutdown', dom.name())
                while dom.isActive():
                    time.sleep(1)
                logger.info('"%s" has shutdown', dom.name())
            else:
                logger.error('"%s" is running, cannot perform offline migration', dom.name())
                continue
        try:
            new_dom = dom.migrate(dst_conn, flags, None, None, 0)
            if offline_migration and auto_start and not new_dom.isActive():
                logger.info('Starting "%s" after offline migration', new_dom.name())
                new_dom.create()
        except libvirt.libvirtError as e:
            logger.error('Migration of "%s" from "%s" to "%s" failed', dom.name(), src_conn.getURI(), dst_conn.getURI(), exc_info=e)
            # Check for a couple of seconds if the domain has shutdown
            for _ in range(5):
                if not dom.isActive():
                    logger.warning('Starting "%s" after migration failure', dom.name())
                    dom.create()
                    break
                time.sleep(1)
