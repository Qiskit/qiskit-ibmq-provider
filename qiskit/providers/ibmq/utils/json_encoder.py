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

# pylint: disable=method-hidden

"""Custom JSON encoders."""

import json
from typing import Any

from qiskit.circuit.parameterexpression import ParameterExpression


class IQXJsonEncoder(json.JSONEncoder):
    """A json encoder for qobj"""

    def encode(self, o: Any) -> str:
        """
        Return a JSON string representation of a Python data structure.

        Convert dictionary to contain only JSON serializable types. For example,
        if the key is a Parameter we convert it to a string.
        """
        if isinstance(o, dict):
            param_bind_str = {}
            for key in o.keys():
                value = self.encode(o[key])

                if type(key) in set([str, int, float, bool]) or key is None:
                    param_bind_str[key] = value
                else:
                    param_bind_str[str(key)] = value
            return super().encode(param_bind_str)
        elif isinstance(o, list):
            return super().encode([self.encode(p) for p in o])
        else:
            return super().encode(o)

    def default(self, o: Any) -> Any:
        # Convert numpy arrays:
        if hasattr(o, 'tolist'):
            return o.tolist()
        # Use Qobj complex json format:
        if isinstance(o, complex):
            return (o.real, o.imag)
        if isinstance(o, ParameterExpression):
            try:
                return float(o)
            except (TypeError, RuntimeError):
                val = complex(o)
                return val.real, val.imag
        return json.JSONEncoder.default(self, o)
