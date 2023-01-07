import inspect
import logging
import os
from typing import Dict, List, Optional

import libvirt

from .libvirt import get_migrate_flags

try:
    import tomllib as toml
except ModuleNotFoundError:
    import toml

logger = logging.getLogger(__name__)

DEFAULT_HOST_GROUP = 'live'
DEFAULT_SAME_GROUP_FLAGS = (libvirt.VIR_MIGRATE_PERSIST_DEST | libvirt.VIR_MIGRATE_UNDEFINE_SOURCE |
                            libvirt.VIR_MIGRATE_LIVE | libvirt.VIR_MIGRATE_PEER2PEER |
                            libvirt.VIR_MIGRATE_TUNNELLED)
DEFAULT_DIFFERENT_GROUP_FLAGS = (libvirt.VIR_MIGRATE_PERSIST_DEST | libvirt.VIR_MIGRATE_UNDEFINE_SOURCE |
                                 libvirt.VIR_MIGRATE_OFFLINE)


class BaseConfig:
    __slots__ = ()

    def __repr__(self):
        attrs = []
        for k in self.__slots__:
            attrs.append(f'{k}={repr(getattr(self, k))}')
        return f'{self.__class__.__name__}({", ".join(attrs)})'


class HostConfig(BaseConfig):
    __slots__ = ('name', 'uri', 'group')

    def __init__(
        self,
        name: str,
        group: Optional[str] = None,
        address: Optional[str] = None,
        user: Optional[str] = 'root',
        port: Optional[int] = 22,
        path: Optional[str] = 'system',
        params: Optional[List[str]] = None,
        uri: Optional[str] = None,
    ):
        self.name = name
        self.group = group or DEFAULT_HOST_GROUP
        if params is None:
            params = ["no_tty=1"]
        if not address and not uri:
            address = name
        if not uri:
            # Not using urllib.parse.urlencode because I'm not sure if we actually need to encode them
            # In addition I want the params argument to be a list, not a key-value pair (makes config file messy)
            uri_params = ''
            if params:
                uri_params = f'?{params[0]}'
                if len(params) > 1:
                    uri_params += f'&{"&".join(params[1:])}'
            self.uri = "qemu+ssh://{user}@{host}{port}/{path}{params}".format(
                user=user,
                host=address,
                port=f':{port}' if port != 22 else '',
                path=path,
                params=uri_params,
            )
        else:
            self.uri = uri

    def __eq__(self, other):
        if not isinstance(other, HostConfig):
            return False
        return self.name == other.name and self.uri == other.uri


class GroupConfig(BaseConfig):
    __slots__ = ('name', 'same_group_flags', 'different_group_flags')

    def __init__(
        self,
        name: str,
        same_group_flags: Optional[List[str]] = None,
        different_group_flags: Optional[List[str]] = None,
    ):
        self.name = name
        self.same_group_flags: int = DEFAULT_SAME_GROUP_FLAGS
        if same_group_flags is not None:
            self.same_group_flags = get_migrate_flags(same_group_flags)

        self.different_group_flags: int = DEFAULT_DIFFERENT_GROUP_FLAGS
        if different_group_flags is not None:
            self.different_group_flags = get_migrate_flags(different_group_flags)

    def __repr__(self) -> str:
        attrs = (
            f'name={repr(self.name)}',
            f'same_group_flags=0b{self.same_group_flags:b}',
            f'different_group_flags=0b{self.different_group_flags:b}',
        )
        return f'{self.__class__.__name__}({", ".join(attrs)})'


class Config(BaseConfig):
    __slots__ = ('hosts', 'groups')

    def __init__(
        self,
        hosts: Dict[str, HostConfig],
        groups: Dict[str, GroupConfig],
    ):
        self.hosts = hosts

        self.groups = {DEFAULT_HOST_GROUP: GroupConfig(DEFAULT_HOST_GROUP)}
        for k, v in groups.items():
            self.groups[k] = v

    @classmethod
    def from_dict(cls, data: dict):
        groups = {}
        groups_spec = inspect.signature(GroupConfig.__init__)
        groups_params = {k for k in groups_spec.parameters.keys() if k != 'self'}
        for name, values in data.get('groups', {}).items():
            kwargs = {"name": name}
            for k, v in values.items():
                if k not in groups_params:
                    logger.warning('Group "%s" contains unknown parameter "%s"', name, k)
                    continue
                kwargs[k] = v
            groups[name] = GroupConfig(**kwargs)

        hosts = {}
        hosts_spec = inspect.signature(HostConfig.__init__)
        hosts_params = {k for k in hosts_spec.parameters.keys() if k != 'self'}
        for name, values in data.get('hosts', {}).items():
            kwargs = {"name": name}
            for k, v in values.items():
                if k not in hosts_params:
                    logger.warning('Host "%s" contains unknown parameter "%s"', name, k)
                    continue
                kwargs[k] = v
            if 'group' not in kwargs:
                kwargs['group'] = DEFAULT_HOST_GROUP
            elif kwargs['group'] not in groups:
                raise Exception(f'Host "{name}" cannot be assigned undefined group "{kwargs["group"]}"')

            hosts[name] = HostConfig(**kwargs)

        if len(hosts) == 0 or 'localhost' in hosts and len(hosts) == 1:
            raise Exception('No hosts in configuration')

        if 'localhost' not in hosts:
            hosts['localhost'] = HostConfig(
                name="localhost",
                uri="qemu:///system",
            )

        return cls(
            hosts=hosts,
            groups=groups,
        )

    @classmethod
    def from_file(cls, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find config file: {file_path}")
        open_mode = 'rb' if toml.__name__ == 'tomllib' else 'r'
        with open(file_path, open_mode) as f:
            return cls.from_dict(toml.load(f))
