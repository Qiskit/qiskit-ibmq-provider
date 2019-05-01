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

"""Utilities related to the IBMQ Provider."""

from qiskit.qobj import QobjHeader


def update_qobj_config(qobj, backend_options=None, noise_model=None):
    """Update a Qobj configuration from options and noise model.

    Args:
        qobj (Qobj): description of job
        backend_options (dict): backend options
        noise_model (NoiseModel): noise model

    Returns:
        Qobj: qobj.
    """
    config = qobj.config.as_dict()

    # Append backend options to configuration.
    if backend_options:
        for key, val in backend_options.items():
            config[key] = val

    # Append noise model to configuration.
    if noise_model:
        config['noise_model'] = noise_model.as_dict(serializable=True)

    # Update the Qobj configuration.
    qobj.config = QobjHeader.from_dict(config)

    return qobj
