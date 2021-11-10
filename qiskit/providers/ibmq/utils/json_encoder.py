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

    def __encode(self, param: Any) -> Any:
        """
        Convert dictionary to contain only JSON serializable types. For example,
        if the key is a Parameter we convert it to a string.
        """
        if isinstance(param, dict):
            param_bind_str = {}
            for key in param.keys():
                value = self.__encode(param[key])

                if isinstance(key, (bool, float, int, str)) or key is None:
                    param_bind_str[key] = value
                else:
                    param_bind_str[str(key)] = value
            return param_bind_str
        elif isinstance(param, list):
            return [self.__encode(p) for p in param]
        else:
            return param

    def encode(self, o: Any) -> str:
        """
        Return a JSON string representation of a Python data structure.
        """
        new_o = self.__encode(o)
        return super().encode(new_o)

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
