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

from qiskit.qobj import QobjHeader


def _serialize_noise_model(config):
    """Traverse the dictionary looking for noise_model keys and apply
       a transformation so it can be serialized.

       Args:
           config (dict): The dictionary to traverse

       Returns:
           dict: The transformed dictionary
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


def update_qobj_config(qobj, backend_options=None, noise_model=None):
    """Update a Qobj configuration from options and noise model.

    Args:
        qobj (Qobj): description of job
        backend_options (dict): backend options
        noise_model (NoiseModel): noise model

    Returns:
        Qobj: qobj.
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
