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

"""Utility functions for the runtime service."""

import json
from typing import Any
import base64
import io
import zlib

import dill
import numpy as np

from qiskit.result import Result
from qiskit.circuit import QuantumCircuit, qpy_serialization


class RuntimeEncoder(json.JSONEncoder):
    """JSON Encoder used by runtime service."""

    def default(self, obj: Any) -> Any:  # pylint: disable=arguments-differ
        if isinstance(obj, np.ndarray):
            np_buffer = io.BytesIO()
            np.save(np_buffer, obj, allow_pickle=False)
            np_buffer.seek(0)
            encoded = base64.standard_b64encode(zlib.compress(np_buffer.read()))
            np_buffer.close()
            return {'__type__': 'ndarray', '__value__': encoded.decode('utf-8')}
        if isinstance(obj, complex):
            return {'__type__': 'complex', '__value__': [obj.real, obj.imag]}
        if isinstance(obj, QuantumCircuit):
            # Serialize, compress, encode.
            qpy_buffer = io.BytesIO()
            qpy_serialization.dump(obj, qpy_buffer)
            qpy_buffer.seek(0)
            encoded = base64.standard_b64encode(zlib.compress(qpy_buffer.read()))
            qpy_buffer.close()
            return {'__type__': 'qpy', '__value__': encoded.decode('utf-8')}
        if isinstance(obj, Result):
            return {'__type__': 'result', '__value__': obj.to_dict()}
        if hasattr(obj, 'to_json'):
            return {'__type__': 'to_json', '__value__': obj.to_json()}
        if hasattr(obj, '__class__'):
            encoded = base64.standard_b64encode(dill.dumps(obj))
            return {'__type__': 'dill', '__value__': encoded.decode('utf-8')}

        return super().default(obj)


class RuntimeDecoder(json.JSONDecoder):
    """JSON Decoder used by runtime service."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj: Any) -> Any:
        """Called to decode object."""
        if '__type__' in obj:
            if obj['__type__'] == 'complex':
                val = obj['__value__']
                return val[0] + 1j * val[1]
            if obj['__type__'] == 'ndarray':
                np_buffer = io.BytesIO()
                np_buffer.write(zlib.decompress(base64.standard_b64decode(obj['__value__'])))
                np_buffer.seek(0)
                data = np.load(np_buffer)
                np_buffer.close()
                return data
            if obj['__type__'] == 'qpy':
                qpy_buffer = io.BytesIO()
                qpy_buffer.write(zlib.decompress(base64.standard_b64decode(obj['__value__'])))
                qpy_buffer.seek(0)
                data = qpy_serialization.load(qpy_buffer)[0]
                qpy_buffer.close()
                return data
            if obj['__type__'] == 'result':
                return Result.from_dict(obj['__value__'])
            if obj['__type__'] == 'to_json':
                return obj['__value__']
            if obj['__type__'] == 'dill':
                decoded = base64.standard_b64decode(obj['__value__'])
                return dill.loads(decoded)
        return obj
