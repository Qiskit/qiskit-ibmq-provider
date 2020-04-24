# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Custom JSON decoder."""

from typing import Dict, Union, List


def decode_pulse_qobj(pulse_qobj: Dict) -> None:
    """Decode a pulse Qobj.

    Args:
        pulse_qobj: Qobj to be decoded.
    """
    for item in pulse_qobj['config']['pulse_library']:
        _decode_pulse_library_item(item)

    for exp in pulse_qobj['experiments']:
        for instr in exp['instructions']:
            _decode_pulse_qobj_instr(instr)


def decode_pulse_backend_config(config: Dict) -> None:
    """Decode pulse backend configuration data.

    Args:
        config: A ``PulseBackendConfiguration`` in dictionary format.
    """
    for u_channle_list in config['u_channel_lo']:
        for u_channle_lo in u_channle_list:
            u_channle_lo['scale'] = _to_complex(u_channle_lo['scale'])


def decode_pulse_defaults(defaults: Dict) -> None:
    """Decode pulse defaults data.

    Args:
        defaults: A ``PulseDefaults`` in dictionary format.
    """
    for item in defaults['pulse_library']:
        _decode_pulse_library_item(item)

    for cmd in defaults['cmd_def']:
        if 'sequence' in cmd:
            for instr in cmd['sequence']:
                _decode_pulse_qobj_instr(instr)


def _to_complex(value: Union[List[float], complex]) -> complex:
    """Convert the input value to type ``complex``.

    Args:
        value: Value to be converted.

    Returns:
        Input value in ``complex``.

    Raises:
        TypeError: If the input value is not in the expected format.
    """
    if isinstance(value, list) and len(value) == 2:
        return complex(value[0], value[1])
    elif isinstance(value, complex):
        return value

    raise TypeError("{} is not in a valid complex number format.".format(value))


def _decode_pulse_library_item(pulse_library_item: Dict) -> None:
    """Decode a pulse library item.

    Args:
        pulse_library_item: A ``PulseLibraryItem`` in dictionary format.
    """
    pulse_library_item['samples'] =\
        [_to_complex(sample) for sample in pulse_library_item['samples']]


def _decode_pulse_qobj_instr(pulse_qobj_instr: Dict) -> None:
    """Decode a pulse Qobj instruction.

    Args:
        pulse_qobj_instr: A ``PulseQobjInstruction`` in dictionary format.
    """
    if 'val' in pulse_qobj_instr:
        pulse_qobj_instr['val'] = _to_complex(pulse_qobj_instr['val'])
    if 'parameters' in pulse_qobj_instr and 'amp' in pulse_qobj_instr['parameters']:
        pulse_qobj_instr['parameters']['amp'] = _to_complex(pulse_qobj_instr['parameters']['amp'])
