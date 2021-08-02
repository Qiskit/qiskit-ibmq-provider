# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# pylint: disable=method-hidden
# pylint: disable=arguments-differ

"""Utility functions for experiment testing."""

from typing import Any
import json

import numpy as np


class ExperimentEncoder(json.JSONEncoder):
    """A test json encoder for experiments"""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, complex):
            return {'__type__': 'complex', '__value__': [obj.real, obj.imag]}
        if hasattr(obj, 'tolist'):
            return {'__type__': 'array', '__value__': obj.tolist()}

        return json.JSONEncoder.default(self, obj)


class ExperimentDecoder(json.JSONDecoder):
    """JSON Decoder for Numpy arrays and complex numbers."""

    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        """Object hook."""
        if "__type__" in obj:
            if obj["__type__"] == "complex":
                val = obj["__value__"]
                return val[0] + 1j * val[1]
            if obj["__type__"] == "array":
                return np.array(obj["__value__"])
        return obj
