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

import dateutil.parser

from .converters import utc_to_local


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


def decode_backend_properties(properties: Dict) -> None:
    """Decode backend properties.

    Args:
        properties: A ``BackendProperties`` in dictionary format.
    """
    properties['last_update_date'] = dateutil.parser.isoparse(properties['last_update_date'])
    for qubit in properties['qubits']:
        for nduv in qubit:
            nduv['date'] = dateutil.parser.isoparse(nduv['date'])
    for gate in properties['gates']:
        for param in gate['parameters']:
            param['date'] = dateutil.parser.isoparse(param['date'])
    for gen in properties['general']:
        gen['date'] = dateutil.parser.isoparse(gen['date'])


def decode_backend_configuration(config: Dict) -> None:
    """Decode backend configuration.

    Args:
        config: A ``QasmBackendConfiguration`` or ``PulseBackendConfiguration``
            in dictionary format.
    """
    config['online_date'] = dateutil.parser.isoparse(config['online_date'])

    if 'u_channel_lo' in config:
        for u_channle_list in config['u_channel_lo']:
            for u_channle_lo in u_channle_list:
                u_channle_lo['scale'] = _to_complex(u_channle_lo['scale'])


def decode_result(result: Dict) -> None:
    """Decode result data.

    Args:
        result: A `Result` in dictionary format.
    """
    if 'date' in result:
        if isinstance(result['date'], str):
            result['date'] = dateutil.parser.isoparse(result['date'])
        result['date'] = utc_to_local(result['date'])


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
