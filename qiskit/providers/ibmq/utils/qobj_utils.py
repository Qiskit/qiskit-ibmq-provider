# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Utilities related to Qobj."""

from typing import Dict, Any, Optional, Union, List

from qiskit.qobj import QobjHeader, QasmQobj, PulseQobj


def _serialize_noise_model(config: Dict[str, Any]) -> Dict[str, Any]:
    """Traverse the dictionary looking for ``noise_model`` keys and apply
    a transformation so it can be serialized.

    Args:
        config: The dictionary to traverse.

    Returns:
        The transformed dictionary.
    """
    for k, v in config.items():
        if isinstance(config[k], dict):
            _serialize_noise_model(config[k])
        else:
            if k == 'noise_model':
                try:
                    config[k] = v.to_dict(serializable=True)
                except AttributeError:
                    # if .to_dict() fails is probably because the noise_model
                    # has been already transformed elsewhere
                    pass

    return config


def update_qobj_config(
        qobj: Union[QasmQobj, PulseQobj],
        backend_options: Optional[Dict] = None,
        noise_model: Any = None
) -> Union[QasmQobj, PulseQobj]:
    """Update a ``Qobj`` configuration from backend options and a noise model.

    Args:
        qobj: Description of the job.
        backend_options: Backend options.
        noise_model: Noise model.

    Returns:
        The updated ``Qobj``.
    """
    config = qobj.config.to_dict()

    # Append backend options to configuration.
    if backend_options:
        for key, val in backend_options.items():
            config[key] = val

    # Append noise model to configuration. Overwrites backend option
    if noise_model:
        config['noise_model'] = noise_model

    # Look for noise_models in the config, and try to transform them
    config = _serialize_noise_model(config)

    # Update the Qobj configuration.
    qobj.config = QobjHeader.from_dict(config)

    return qobj


def dict_to_qobj(qobj_dict: Dict) -> Union[QasmQobj, PulseQobj]:
    """Convert a Qobj in dictionary format to an instance.

    Args:
        qobj_dict: Qobj in dictionary format.

    Returns:
        The corresponding QasmQobj or PulseQobj instance.
    """
    if qobj_dict['type'] == 'PULSE':
        _decode_pulse_qobj(qobj_dict)   # Convert to proper types.
        return PulseQobj.from_dict(qobj_dict)
    return QasmQobj.from_dict(qobj_dict)


def _decode_pulse_qobj(pulse_qobj: Dict) -> None:
    """Decode a pulse Qobj.

    Args:
        pulse_qobj: Qobj to be decoded.
    """
    pulse_library = pulse_qobj['config']['pulse_library']
    for lib in pulse_library:
        lib['samples'] = [_to_complex(sample) for sample in lib['samples']]

    for exp in pulse_qobj['experiments']:
        for instr in exp['instructions']:
            if 'val' in instr:
                instr['val'] = _to_complex(instr['val'])
            if 'parameters' in instr and 'amp' in instr['parameters']:
                instr['parameters']['amp'] = _to_complex(instr['parameters']['amp'])


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
