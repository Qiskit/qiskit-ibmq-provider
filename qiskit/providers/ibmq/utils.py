# -*- coding: utf-8 -*-

# Copyright 2019, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Utilities related to the IBMQ Provider."""

import json

from numpy import ndarray

from qiskit.qobj import QobjHeader


class AerJSONEncoder(json.JSONEncoder):
    """JSON encoder for NumPy arrays and complex numbers.

    This functions as the standard JSON Encoder but adds support
    for encoding:
        complex numbers z as lists [z.real, z.imag]
        ndarrays as nested lists.
    """

    # pylint: disable=method-hidden,arguments-differ
    def default(self, obj):
        if isinstance(obj, ndarray):
            return obj.tolist()
        if isinstance(obj, complex):
            return [obj.real, obj.imag]
        if hasattr(obj, "as_dict"):
            return obj.as_dict()
        return super().default(obj)


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
        config['noise_model'] = json.loads(json.dumps(noise_model,
                                                      cls=AerJSONEncoder))

    # Update the Qobj configuration.
    qobj.config = QobjHeader.from_dict(config)

    return qobj
