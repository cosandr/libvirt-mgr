# Minimal libvirt VM manager

Collection of scripts for managing libvirt VMs.


### Requirements

If using Python <3.11, `toml` is required. On Python 3.11 and later `tomllib` from stdlib is used.

```sh
# RHEL
dnf install -y python3-toml python3-libvirt
# Debian
apt install -y python3-toml python3-libvirt
# Arch
pacman -S python-toml libvirt-python
```

Passwordless SSH is required for the default configuration which uses SSH transport.


### Installation

Install with pip, prefer requirements from package manager

```sh
pip install --no-deps --prefix /usr/local git+https://github.com/cosandr/libvirt-mgr.git
```


### Configuration

Default config path is `/etc/libvirt-mgr/config.toml`, [example file](./examples/config.toml).


### Testing

Requires `pytest` and `pytest-cov`

```sh
pytest
pytest --cov
```

Run from source with

```sh
python -m libvirt_mgr.virtmgr --help
```


### License

GNU General Public License v2 or later (GPLv2+)


### Author

Andrei Costescu
