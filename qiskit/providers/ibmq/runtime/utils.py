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
import numpy as np

from qiskit.compiler import assemble
from qiskit.assembler.disassemble import disassemble
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.qobj import QasmQobj


class RuntimeEncoder(json.JSONEncoder):
    """JSON Encoder for Numpy arrays, complex numbers, and circuits."""

    def default(self, obj: Any) -> Any:
        if hasattr(obj, 'tolist'):
            return {'type': 'array', 'value': obj.tolist()}
        if isinstance(obj, complex):
            return {'type': 'complex', 'value': [obj.real, obj.imag]}
        if isinstance(obj, QuantumCircuit):
            return {'type': 'circuits', 'value': assemble(obj).to_dict()}
        return super().default(obj)


class RuntimeDecoder(json.JSONDecoder):
    """JSON Decoder for Numpy arrays, complex numbers, and circuits."""

    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if 'type' in obj:
            if obj['type'] == 'complex':
                val = obj['value']
                return val[0] + 1j * val[1]
            if obj['type'] == 'array':
                return np.array(obj['value'])
            if obj['type'] == 'circuits':
                circuits, _, _ = disassemble(QasmQobj.from_dict(obj['value']))
                if len(circuits) == 1:
                    return circuits[0]
                return circuits
        return obj
