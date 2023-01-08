import argparse

import libvirt
import pytest

from libvirt_mgr import migrate
from libvirt_mgr.utils.config import Config, HostConfig


def test_launch_migrate():
    config = Config(
        groups={},
        hosts={
            "host01": HostConfig(
                name="host01",
            ),
            "host02": HostConfig(
                name="host02",
            ),
        },
    )
    args = argparse.Namespace(
        src_host='idontexist',
        name=None,
        all=False,
        dst_host=None,
        dst_group=None,
    )
    with pytest.raises(Exception) as e:
        migrate.launch_migrate(args, config)
    assert str(e.value) == 'Source host "idontexist" not found in configuration'

    args = argparse.Namespace(
        src_host='host01',
        name=None,
        all=False,
        dst_host='idontexist',
        dst_group=None,
    )
    with pytest.raises(Exception) as e:
        migrate.launch_migrate(args, config)
    assert str(e.value) == 'Destination host "idontexist" not found in configuration'

    args = argparse.Namespace(
        src_host='host01',
        name=None,
        all=False,
        dst_host='host01',
        dst_group=None,
    )
    with pytest.raises(Exception) as e:
        migrate.launch_migrate(args, config)
    assert str(e.value) == 'Source and destination host cannot be the same'

    # Assert failure to connect
    args = argparse.Namespace(
        src_host='host01',
        name=None,
        all=False,
        dst_host='host02',
        dst_group=None,
    )
    with pytest.raises(libvirt.libvirtError) as e:
        migrate.launch_migrate(args, config)
