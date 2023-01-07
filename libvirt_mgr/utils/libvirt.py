from typing import List

import libvirt


def get_migrate_flags(flags: List[str]) -> int:
    """Returns migrate flags OR'd together from a list of names as strings"""
    ret = 0
    for f in flags:
        val = getattr(libvirt, f'VIR_MIGRATE_{f.upper()}', None)
        if not val:
            raise Exception(f'No flag "{f.upper()}" exists')
        ret |= val
    return ret
