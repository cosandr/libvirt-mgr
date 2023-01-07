import pathlib

import libvirt
import pytest

from libvirt_mgr.utils.config import Config, HostConfig, DEFAULT_SAME_GROUP_FLAGS, DEFAULT_DIFFERENT_GROUP_FLAGS
from libvirt_mgr.utils.libvirt import get_migrate_flags


def test_missing_hosts():
    data = {
        "hosts": {},
    }
    with pytest.raises(Exception) as e:
        Config.from_dict(data)
    assert str(e.value) == "No hosts in configuration"


def test_invalid_file_path():
    with pytest.raises(FileNotFoundError) as e:
        Config.from_file('/i/hope/nobody/has/this')
    assert str(e.value) == "Could not find config file: /i/hope/nobody/has/this"


def test_host_config():
    data = {
        "hosts": {
            "host01": {},
            "host02": {"params": []},
            "host03": {"address": "10.0.10.1"},
            "host04": {
                "address": "10.0.10.4",
                "user": "libvirt",
                "port": 2200,
                "params": ["command=/opt/openssh/bin/ssh", "no_verify=1", "no_tty=0"],
                "path": "notsys",
            },
            "host05": {
                "uri": "test+tcp://localhost:5000/default",
            },
        }
    }
    actual = Config.from_dict(data)
    # Add 1 due to implicit localhost
    assert len(actual.hosts) == len(data['hosts']) + 1
    assert "host01" in actual.hosts
    assert actual.hosts["host01"].uri == 'qemu+ssh://root@host01/system?no_tty=1'
    assert "host02" in actual.hosts
    assert actual.hosts["host02"].uri == 'qemu+ssh://root@host02/system'
    assert "host03" in actual.hosts
    assert actual.hosts["host03"].uri == 'qemu+ssh://root@10.0.10.1/system?no_tty=1'
    assert "host04" in actual.hosts
    assert actual.hosts["host04"].uri == 'qemu+ssh://libvirt@10.0.10.4:2200/notsys?command=/opt/openssh/bin/ssh&no_verify=1&no_tty=0'
    assert "host05" in actual.hosts
    assert actual.hosts["host05"].uri == 'test+tcp://localhost:5000/default'


def test_host_config_unsupported_param(caplog: pytest.LogCaptureFixture):
    data = {
        "hosts": {
            "host01": {
                "idontexist": 42,
            },
        }
    }
    Config.from_dict(data)
    assert 'Host "host01" contains unknown parameter "idontexist"' in caplog.text


def test_host_config_localhost():
    data = {'hosts': {"host01": {}}}
    actual = Config.from_dict(data)
    assert actual.hosts['localhost'].uri == "qemu:///system"

    data = {'hosts': {"localhost": {}}}
    with pytest.raises(Exception) as e:
        Config.from_dict(data)
    assert str(e.value) == "No hosts in configuration"

    data = {'hosts': {"localhost": {"uri": "qemu:///session"}, "host01": {}}}
    actual = Config.from_dict(data)
    assert actual.hosts['localhost'].uri == "qemu:///session"


def test_host_config_eq():
    h1 = HostConfig(name="host01")
    h2 = HostConfig(name="host01")
    assert h1 == h2

    h1 = HostConfig(name="host01")
    h2 = HostConfig(name="host02")
    assert h1 != h2

    h1 = HostConfig(name="host01")
    h2 = HostConfig(name="host01", port=221)
    assert h1 != h2


def test_read_migrate_flags():
    data = [
        {
            "expected": libvirt.VIR_MIGRATE_LIVE,
            "actual": get_migrate_flags(['live']),
        },
        {
            "expected": libvirt.VIR_MIGRATE_LIVE | libvirt.VIR_MIGRATE_PEER2PEER | libvirt.VIR_MIGRATE_TUNNELLED,
            "actual": get_migrate_flags(['live', 'peer2peer', 'tunnelled']),
        },
    ]
    for d in data:
        assert d['actual'] == d['expected']

    with pytest.raises(Exception) as e:
        get_migrate_flags(['notaflag'])
    assert str(e.value) == 'No flag "NOTAFLAG" exists'


def test_groups_config():
    _def_hosts = {"host01": {}}
    # Check if we have the live group by default
    data = {
        "hosts": _def_hosts,
    }
    actual = Config.from_dict(data)
    assert len(actual.groups) == 1
    assert 'live' in actual.groups
    assert actual.groups['live'].same_group_flags == DEFAULT_SAME_GROUP_FLAGS
    assert actual.groups['live'].different_group_flags == DEFAULT_DIFFERENT_GROUP_FLAGS

    # Check that we can add a group
    data = {
        "hosts": _def_hosts,
        "groups": {
            "offline": {},
        },
    }
    actual = Config.from_dict(data)
    assert len(actual.groups) == 2
    assert 'live' in actual.groups
    assert 'offline' in actual.groups

    # Check that we can modify the live group
    data = {
        "hosts": _def_hosts,
        "groups": {
            "live": {
                "same_group_flags": ["live"],
            },
            "offline": {},
        },
    }
    actual = Config.from_dict(data)
    assert len(actual.groups) == 2
    assert 'live' in actual.groups
    assert 'offline' in actual.groups
    assert actual.groups['live'].same_group_flags == libvirt.VIR_MIGRATE_LIVE
    assert actual.groups['live'].different_group_flags == DEFAULT_DIFFERENT_GROUP_FLAGS


def test_host_groups():
    data = {
        "hosts": {
            "host01": {},
        },
    }
    actual = Config.from_dict(data)
    assert actual.hosts['host01'].group == 'live'

    data = {
        "hosts": {
            "host01": {
                "group": "idontexist",
            },
        },
    }
    with pytest.raises(Exception) as e:
        Config.from_dict(data)
    assert str(e.value) == 'Host "host01" cannot be assigned undefined group "idontexist"'

    data = {
        "hosts": {
            "host01": {
                "group": "offline",
            },
        },
        "groups": {
            "offline": {},
        }
    }
    actual = Config.from_dict(data)
    assert actual.hosts['host01'].group == 'offline'

    data = {
        "hosts": {
            "host01": {},
            "host02": {
                "group": "offline",
            },
        },
        "groups": {
            "offline": {},
        }
    }
    actual = Config.from_dict(data)
    assert actual.hosts['host01'].group == 'live'
    assert actual.hosts['host02'].group == 'offline'


def test_config_toml(tmp_path: pathlib.Path):
    config_content = """
[hosts.host01]

[hosts.host02]
params = []

[hosts.host03]
address = "10.0.10.1"

[hosts.host04]
address = "10.0.10.4"
user = "libvirt"
port = 2200
params = ["command=/opt/openssh/bin/ssh", "no_verify=1", "no_tty=0"]
path = "notsys"

[hosts.host05]
uri = "test+tcp://localhost:5000/default"
"""
    d = tmp_path / "config"
    d.mkdir()
    p = d / "config.toml"
    p.write_text(config_content)
    assert p.read_text() == config_content
    actual = Config.from_file(str(p))
    assert "host01" in actual.hosts
    assert actual.hosts["host01"].uri == 'qemu+ssh://root@host01/system?no_tty=1'
    assert "host02" in actual.hosts
    assert actual.hosts["host02"].uri == 'qemu+ssh://root@host02/system'
    assert "host03" in actual.hosts
    assert actual.hosts["host03"].uri == 'qemu+ssh://root@10.0.10.1/system?no_tty=1'
    assert "host04" in actual.hosts
    assert actual.hosts["host04"].uri == 'qemu+ssh://libvirt@10.0.10.4:2200/notsys?command=/opt/openssh/bin/ssh&no_verify=1&no_tty=0'
    assert "host05" in actual.hosts
    assert actual.hosts["host05"].uri == 'test+tcp://localhost:5000/default'
